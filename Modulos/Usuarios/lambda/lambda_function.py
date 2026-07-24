import base64
import json
import os
import uuid

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from cloudshop_common import (
    ApiError,
    correlation_id,
    error_response,
    log_event,
    parse_body,
    required_text,
    require_role,
    response,
    utc_now,
)


USERS_TABLE = os.environ["USERS_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
USER_POOL_ID = os.environ["USER_POOL_ID"]
OFFICIAL_ROLES = ("ADMINISTRADOR", "OPERADOR", "CLIENTE")
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()
_dynamodb = None
_cognito = None


def clients():
    global _dynamodb, _cognito
    if _dynamodb is None:
        _dynamodb = boto3.client("dynamodb")
    if _cognito is None:
        _cognito = boto3.client("cognito-idp")
    return _dynamodb, _cognito


def serialize(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def deserialize(item):
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


def route_action(event):
    method = (event.get("httpMethod") or "").upper()
    resource = event.get("resource") or ""
    mapping = {
        ("GET", "/usuarios"): "LIST",
        ("GET", "/usuarios/{userId}"): "GET",
        ("PUT", "/usuarios/{userId}"): "UPDATE",
        ("DELETE", "/usuarios/{userId}"): "DEACTIVATE",
        ("PATCH", "/usuarios/{userId}/rol"): "CHANGE_ROLE",
    }
    action = mapping.get((method, resource))
    if not action:
        raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")
    return action


def user_id_from(event):
    user_id = (event.get("pathParameters") or {}).get("userId")
    if not user_id:
        raise ApiError(400, "INVALID_INPUT", "userId es obligatorio")
    return user_id


def get_user(user_id):
    dynamodb, _ = clients()
    result = dynamodb.get_item(
        TableName=USERS_TABLE,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    )
    if "Item" not in result:
        raise ApiError(404, "USER_NOT_FOUND", "El usuario no existe")
    return deserialize(result["Item"])


def assert_owner_or_admin(identity, user_id):
    if identity["role"] != "ADMINISTRADOR" and identity["actor_id"] != user_id:
        raise ApiError(403, "FORBIDDEN", "Solo puede consultar o editar su perfil")


def audit_item(identity, action, user_id, result, correlation):
    timestamp = utc_now()
    return {
        "auditId": str(uuid.uuid4()),
        "actorId": identity["actor_id"],
        "action": action,
        "resourceType": "USER",
        "resourceId": user_id,
        "resourceKey": f"USER#{user_id}",
        "occurredAt": timestamp,
        "result": result,
        "correlationId": correlation,
    }


def list_users(event, identity, correlation):
    dynamodb, _ = clients()
    params = event.get("queryStringParameters") or {}
    try:
        limit = min(max(int(params.get("limit", 50)), 1), 100)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "INVALID_INPUT", "limit debe ser un entero") from exc
    request = {"TableName": USERS_TABLE, "Limit": limit}
    if params.get("nextToken"):
        try:
            key = json.loads(
                base64.urlsafe_b64decode(params["nextToken"].encode()).decode()
            )
            request["ExclusiveStartKey"] = key
        except Exception as exc:
            raise ApiError(400, "INVALID_INPUT", "nextToken no es válido") from exc
    result = dynamodb.scan(**request)
    body = {"data": [deserialize(item) for item in result.get("Items", [])]}
    if result.get("LastEvaluatedKey"):
        body["nextToken"] = base64.urlsafe_b64encode(
            json.dumps(result["LastEvaluatedKey"]).encode()
        ).decode()
    return response(200, body, correlation)


def get_user_response(event, identity, correlation):
    user_id = user_id_from(event)
    assert_owner_or_admin(identity, user_id)
    return response(200, {"data": get_user(user_id)}, correlation)


def update_user(event, identity, correlation):
    user_id = user_id_from(event)
    assert_owner_or_admin(identity, user_id)
    body = parse_body(event)
    if set(body) != {"name"}:
        raise ApiError(400, "INVALID_INPUT", "Solo se permite actualizar name")
    name = required_text(body, "name", 160)
    current = get_user(user_id)
    timestamp = utc_now()
    audit = audit_item(identity, "UPDATE_USER", user_id, "EXITOSO", correlation)
    dynamodb, _ = clients()
    dynamodb.transact_write_items(
        TransactItems=[
            {
                "Update": {
                    "TableName": USERS_TABLE,
                    "Key": {"userId": {"S": user_id}},
                    "UpdateExpression": "SET #name = :name, updatedAt = :updated",
                    "ConditionExpression": "updatedAt = :previous AND #status = :active",
                    "ExpressionAttributeNames": {
                        "#name": "name",
                        "#status": "status",
                    },
                    "ExpressionAttributeValues": {
                        ":name": {"S": name},
                        ":updated": {"S": timestamp},
                        ":previous": {"S": current["updatedAt"]},
                        ":active": {"S": "ACTIVE"},
                    },
                }
            },
            {"Put": {"TableName": AUDIT_TABLE, "Item": serialize(audit)}},
        ]
    )
    return response(
        200,
        {"data": {**current, "name": name, "updatedAt": timestamp}},
        correlation,
    )


def deactivate_user(event, identity, correlation):
    user_id = user_id_from(event)
    if identity["actor_id"] == user_id:
        raise ApiError(409, "CONFLICT", "No puede desactivar su propia cuenta administrativa")
    current = get_user(user_id)
    timestamp = utc_now()
    audit = audit_item(identity, "DEACTIVATE_USER", user_id, "EXITOSO", correlation)
    dynamodb, cognito = clients()
    cognito.admin_disable_user(
        UserPoolId=USER_POOL_ID,
        Username=current["username"],
    )
    try:
        dynamodb.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": USERS_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "SET #status = :inactive, updatedAt = :updated",
                        "ConditionExpression": "#status = :active",
                        "ExpressionAttributeNames": {"#status": "status"},
                        "ExpressionAttributeValues": {
                            ":inactive": {"S": "INACTIVE"},
                            ":active": {"S": "ACTIVE"},
                            ":updated": {"S": timestamp},
                        },
                    }
                },
                {"Put": {"TableName": AUDIT_TABLE, "Item": serialize(audit)}},
            ]
        )
    except Exception:
        cognito.admin_enable_user(
            UserPoolId=USER_POOL_ID,
            Username=current["username"],
        )
        raise
    return response(
        200,
        {"data": {**current, "status": "INACTIVE", "updatedAt": timestamp}},
        correlation,
    )


def change_role(event, identity, correlation):
    user_id = user_id_from(event)
    if identity["actor_id"] == user_id:
        raise ApiError(409, "CONFLICT", "No puede cambiar su propio rol")
    body = parse_body(event)
    if set(body) != {"role"} or body["role"] not in OFFICIAL_ROLES:
        raise ApiError(400, "INVALID_INPUT", "role debe ser un rol oficial")
    new_role = body["role"]
    current = get_user(user_id)
    if current["status"] != "ACTIVE":
        raise ApiError(409, "CONFLICT", "No se puede asignar rol a un usuario inactivo")
    if current["role"] == new_role:
        return response(200, {"data": current}, correlation)

    dynamodb, cognito = clients()
    username = current["username"]
    previous_groups = cognito.admin_list_groups_for_user(
        Username=username,
        UserPoolId=USER_POOL_ID,
    ).get("Groups", [])
    previous_official = [
        group["GroupName"]
        for group in previous_groups
        if group.get("GroupName") in OFFICIAL_ROLES
    ]
    for group in previous_official:
        cognito.admin_remove_user_from_group(
            Username=username,
            UserPoolId=USER_POOL_ID,
            GroupName=group,
        )
    cognito.admin_add_user_to_group(
        Username=username,
        UserPoolId=USER_POOL_ID,
        GroupName=new_role,
    )

    timestamp = utc_now()
    audit = audit_item(identity, "CHANGE_USER_ROLE", user_id, "EXITOSO", correlation)
    audit["details"] = {"previousRole": current["role"], "newRole": new_role}
    try:
        dynamodb.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": USERS_TABLE,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "SET #role = :role, updatedAt = :updated",
                        "ConditionExpression": "#role = :previous AND #status = :active",
                        "ExpressionAttributeNames": {
                            "#role": "role",
                            "#status": "status",
                        },
                        "ExpressionAttributeValues": {
                            ":role": {"S": new_role},
                            ":previous": {"S": current["role"]},
                            ":active": {"S": "ACTIVE"},
                            ":updated": {"S": timestamp},
                        },
                    }
                },
                {"Put": {"TableName": AUDIT_TABLE, "Item": serialize(audit)}},
            ]
        )
    except Exception:
        cognito.admin_remove_user_from_group(
            Username=username,
            UserPoolId=USER_POOL_ID,
            GroupName=new_role,
        )
        for group in previous_official:
            cognito.admin_add_user_to_group(
                Username=username,
                UserPoolId=USER_POOL_ID,
                GroupName=group,
            )
        raise
    return response(
        200,
        {"data": {**current, "role": new_role, "updatedAt": timestamp}},
        correlation,
    )


HANDLERS = {
    "LIST": list_users,
    "GET": get_user_response,
    "UPDATE": update_user,
    "DEACTIVATE": deactivate_user,
    "CHANGE_ROLE": change_role,
}


def lambda_handler(event, context):
    correlation = correlation_id(event, context)
    action = None
    identity = {"actor_id": "UNKNOWN"}
    try:
        action = route_action(event)
        allowed_roles = (
            {"ADMINISTRADOR"}
            if action in {"LIST", "DEACTIVATE", "CHANGE_ROLE"}
            else {"ADMINISTRADOR", "OPERADOR", "CLIENTE"}
        )
        identity = require_role(event, allowed_roles)
        log_event(
            "info",
            "user_request",
            correlation,
            action=action,
            actorId=identity["actor_id"],
            role=identity["role"],
        )
        return HANDLERS[action](event, identity, correlation)
    except ApiError as exc:
        log_event(
            "warning",
            "user_request_rejected",
            correlation,
            action=action,
            actorId=identity["actor_id"],
            statusCode=exc.status_code,
            errorCode=exc.code,
        )
        return error_response(exc, correlation)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        status = 409 if code in {"TransactionCanceledException", "ConditionalCheckFailedException"} else 500
        error = ApiError(status, "CONFLICT" if status == 409 else "INTERNAL_ERROR", "No se pudo completar la operación")
        log_event(
            "exception",
            "user_dependency_error",
            correlation,
            action=action,
            statusCode=status,
            errorCode=code,
        )
        return error_response(error, correlation)
    except Exception:
        log_event(
            "exception",
            "user_unexpected_error",
            correlation,
            action=action,
            statusCode=500,
            errorCode="INTERNAL_ERROR",
        )
        return error_response(
            ApiError(500, "INTERNAL_ERROR", "Error interno del servidor"),
            correlation,
        )
