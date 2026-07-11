import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError


USERS_TABLE = os.environ.get("USERS_TABLE", "Users")
AUDIT_TABLE = os.environ.get("AUDIT_TABLE", "UserAudit")
STATUS_INDEX = os.environ.get("STATUS_INDEX", "StatusCreatedAtIndex")
VALID_ROLES = {"ADMINISTRADOR", "OPERADOR", "CLIENTE"}
VALID_STATUSES = {"ACTIVE", "DISABLED"}
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()
dynamodb = boto3.client("dynamodb")


class ApiError(Exception):
    def __init__(self, status_code, code, message):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log_event(level, event_name, **details):
    getattr(LOGGER, level)(json.dumps({"event": event_name, **details}, ensure_ascii=False, default=str))


def serialize_item(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items() if value is not None}


def deserialize_item(item):
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


def response(status_code, body=None):
    payload = "" if body is None else json.dumps(body, ensure_ascii=False, default=str)
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,Accept",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
        },
        "body": payload,
    }


def error_response(status_code, code, message):
    return response(status_code, {"error": {"code": code, "message": message}})


def parse_body(event):
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError as exc:
        raise ApiError(400, "INVALID_JSON", "El cuerpo debe ser JSON valido") from exc
    if not isinstance(body, dict):
        raise ApiError(400, "INVALID_INPUT", "El cuerpo debe ser un objeto JSON")
    return body


def required_text(body, field, max_length=160):
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "INVALID_INPUT", f"{field} es obligatorio")
    value = value.strip()
    if len(value) > max_length:
        raise ApiError(400, "INVALID_INPUT", f"{field} excede la longitud permitida")
    return value


def optional_text(body, field, max_length=160):
    value = body.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "INVALID_INPUT", f"{field} debe ser texto")
    value = value.strip()
    if len(value) > max_length:
        raise ApiError(400, "INVALID_INPUT", f"{field} excede la longitud permitida")
    return value


def validate_email(value):
    if not EMAIL_PATTERN.match(value):
        raise ApiError(400, "INVALID_INPUT", "email no es valido")
    return value.lower()


def normalize_role(value):
    role = str(value or "").strip().upper()
    if role not in VALID_ROLES:
        raise ApiError(400, "INVALID_INPUT", "role no es valido")
    return role


def validate_user_payload(body, partial=False):
    validated = {}
    if not partial or "name" in body:
        validated["name"] = required_text(body, "name", 160)
    if not partial or "email" in body:
        validated["email"] = validate_email(required_text(body, "email", 254))
    if not partial or "role" in body:
        validated["role"] = normalize_role(body.get("role"))
    if "phone" in body:
        phone = optional_text(body, "phone", 40)
        if phone is not None:
            validated["phone"] = phone
    if partial and not validated:
        raise ApiError(400, "INVALID_INPUT", "Debe enviar al menos un campo actualizable")
    return validated


def path_user_id(event):
    user_id = (event.get("pathParameters") or {}).get("userId")
    if not user_id:
        raise ApiError(400, "INVALID_INPUT", "userId es obligatorio")
    return user_id


def actor_from_event(event):
    identity = ((event.get("requestContext") or {}).get("identity") or {})
    return identity.get("userArn") or identity.get("principalOrgId") or "UNKNOWN"


def audit(event, action, user_id, result="EXITOSO"):
    item = {
        "auditId": str(uuid.uuid4()),
        "usuario": actor_from_event(event),
        "accion": action,
        "resourceType": "USER",
        "resourceId": user_id,
        "fecha": utc_now(),
        "resultado": result,
    }
    dynamodb.put_item(TableName=AUDIT_TABLE, Item=serialize_item(item))


def get_user_item(user_id):
    result = dynamodb.get_item(TableName=USERS_TABLE, Key={"userId": {"S": user_id}}, ConsistentRead=True)
    item = result.get("Item")
    if not item:
        raise ApiError(404, "USER_NOT_FOUND", "El usuario no existe")
    return deserialize_item(item)


def create_user(event):
    body = validate_user_payload(parse_body(event))
    timestamp = utc_now()
    user = {
        "userId": str(uuid.uuid4()),
        **body,
        "status": "ACTIVE",
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    dynamodb.put_item(TableName=USERS_TABLE, Item=serialize_item(user), ConditionExpression="attribute_not_exists(userId)")
    audit(event, "CREATE_USER", user["userId"])
    log_event("info", "user_created", userId=user["userId"], role=user["role"])
    return response(201, {"data": user})


def list_users(event):
    params = event.get("queryStringParameters") or {}
    status = str(params.get("status", "ACTIVE")).upper()
    if status not in VALID_STATUSES:
        raise ApiError(400, "INVALID_INPUT", "status no es valido")
    result = dynamodb.query(
        TableName=USERS_TABLE,
        IndexName=STATUS_INDEX,
        KeyConditionExpression="#status = :status",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": {"S": status}},
        ScanIndexForward=False,
    )
    items = [deserialize_item(item) for item in result.get("Items", [])]
    return response(200, {"data": items, "count": len(items)})


def get_user(event):
    return response(200, {"data": get_user_item(path_user_id(event))})


def update_user(event):
    user_id = path_user_id(event)
    current = get_user_item(user_id)
    if current.get("status") == "DISABLED":
        raise ApiError(409, "USER_DISABLED", "El usuario esta deshabilitado")
    updates = validate_user_payload(parse_body(event), partial=True)
    updated = {**current, **updates, "updatedAt": utc_now()}
    dynamodb.put_item(
        TableName=USERS_TABLE,
        Item=serialize_item(updated),
        ConditionExpression="attribute_exists(userId) AND #status = :active AND updatedAt = :previousUpdatedAt",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":active": {"S": "ACTIVE"}, ":previousUpdatedAt": {"S": current["updatedAt"]}},
    )
    audit(event, "UPDATE_USER", user_id)
    log_event("info", "user_updated", userId=user_id)
    return response(200, {"data": updated})


def disable_user(event):
    user_id = path_user_id(event)
    timestamp = utc_now()
    result = dynamodb.update_item(
        TableName=USERS_TABLE,
        Key={"userId": {"S": user_id}},
        UpdateExpression="SET #status = :disabled, disabledAt = :disabledAt, updatedAt = :updatedAt",
        ConditionExpression="attribute_exists(userId) AND #status = :active",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":disabled": {"S": "DISABLED"},
            ":active": {"S": "ACTIVE"},
            ":disabledAt": {"S": timestamp},
            ":updatedAt": {"S": timestamp},
        },
        ReturnValues="ALL_NEW",
    )
    user = deserialize_item(result["Attributes"])
    audit(event, "DISABLE_USER", user_id)
    log_event("info", "user_disabled", userId=user_id)
    return response(200, {"data": user})


def route(event):
    method = (event.get("httpMethod") or "").upper()
    resource = event.get("resource") or ""
    routes = {
        ("POST", "/usuarios"): create_user,
        ("GET", "/usuarios"): list_users,
        ("GET", "/usuarios/{userId}"): get_user,
        ("PUT", "/usuarios/{userId}"): update_user,
        ("DELETE", "/usuarios/{userId}"): disable_user,
    }
    handler = routes.get((method, resource))
    if not handler:
        raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")
    return handler(event)


def lambda_handler(event, context):
    try:
        log_event("info", "users_request", requestId=context.aws_request_id, method=event.get("httpMethod"), resource=event.get("resource"))
        return route(event)
    except ApiError as exc:
        log_event("warning", "users_request_rejected", requestId=context.aws_request_id, statusCode=exc.status_code, errorCode=exc.code)
        return error_response(exc.status_code, exc.code, exc.message)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        log_event("exception", "users_aws_error", requestId=context.aws_request_id, errorCode=error_code)
        if error_code in {"ConditionalCheckFailedException", "TransactionCanceledException"}:
            return error_response(409, "USER_CONFLICT", "El usuario no existe, esta deshabilitado o fue modificado")
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    except Exception:
        log_event("exception", "users_unexpected_error", requestId=context.aws_request_id)
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
