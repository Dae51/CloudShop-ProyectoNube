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


STORES_TABLE = os.environ["STORES_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()
_dynamodb = None


def client():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.client("dynamodb")
    return _dynamodb


def serialize(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def deserialize(item):
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


def route_action(event):
    key = ((event.get("httpMethod") or "").upper(), event.get("resource") or "")
    action = {
        ("POST", "/tiendas"): "CREATE",
        ("GET", "/tiendas"): "LIST",
        ("GET", "/tiendas/{storeId}"): "GET",
        ("PUT", "/tiendas/{storeId}"): "UPDATE",
        ("DELETE", "/tiendas/{storeId}"): "DEACTIVATE",
    }.get(key)
    if not action:
        raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")
    return action


def store_id_from(event):
    value = (event.get("pathParameters") or {}).get("storeId")
    if not value:
        raise ApiError(400, "INVALID_INPUT", "storeId es obligatorio")
    return value


def validate_store(body):
    if set(body) != {"name", "description"}:
        raise ApiError(400, "INVALID_INPUT", "Se requieren name y description")
    return {
        "name": required_text(body, "name", 160),
        "description": required_text(body, "description", 1000),
    }


def get_store(store_id, include_inactive=False):
    result = client().get_item(
        TableName=STORES_TABLE,
        Key={"storeId": {"S": store_id}},
        ConsistentRead=True,
    )
    if "Item" not in result:
        raise ApiError(404, "STORE_NOT_FOUND", "La tienda no existe")
    store = deserialize(result["Item"])
    if store["status"] != "ACTIVE" and not include_inactive:
        raise ApiError(404, "STORE_NOT_FOUND", "La tienda no existe")
    return store


def audit(identity, action, store_id, correlation):
    timestamp = utc_now()
    return {
        "auditId": str(uuid.uuid4()),
        "actorId": identity["actor_id"],
        "action": action,
        "resourceType": "STORE",
        "resourceId": store_id,
        "resourceKey": f"STORE#{store_id}",
        "occurredAt": timestamp,
        "result": "EXITOSO",
        "correlationId": correlation,
    }


def write_store_and_audit(store, previous_updated_at, audit_item):
    condition = "attribute_not_exists(storeId)"
    values = None
    if previous_updated_at:
        condition = "#status = :active AND updatedAt = :previous"
        values = {
            ":active": {"S": "ACTIVE"},
            ":previous": {"S": previous_updated_at},
        }
    put = {
        "TableName": STORES_TABLE,
        "Item": serialize(store),
        "ConditionExpression": condition,
    }
    if values:
        put["ExpressionAttributeNames"] = {"#status": "status"}
        put["ExpressionAttributeValues"] = values
    client().transact_write_items(
        TransactItems=[
            {"Put": put},
            {"Put": {"TableName": AUDIT_TABLE, "Item": serialize(audit_item)}},
        ]
    )


def create_store(event, identity, correlation):
    values = validate_store(parse_body(event))
    timestamp = utc_now()
    store = {
        "storeId": str(uuid.uuid4()),
        **values,
        "status": "ACTIVE",
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    write_store_and_audit(
        store,
        None,
        audit(identity, "CREATE_STORE", store["storeId"], correlation),
    )
    return response(201, {"data": store}, correlation)


def list_stores(event, identity, correlation):
    include_inactive = (
        identity["role"] == "ADMINISTRADOR"
        and str((event.get("queryStringParameters") or {}).get("includeInactive", "")).lower()
        == "true"
    )
    request = {"TableName": STORES_TABLE}
    if not include_inactive:
        request.update(
            {
                "FilterExpression": "#status = :active",
                "ExpressionAttributeNames": {"#status": "status"},
                "ExpressionAttributeValues": {":active": {"S": "ACTIVE"}},
            }
        )
    items = [deserialize(item) for item in client().scan(**request).get("Items", [])]
    return response(200, {"data": items}, correlation)


def get_store_response(event, identity, correlation):
    store = get_store(store_id_from(event), identity["role"] == "ADMINISTRADOR")
    return response(200, {"data": store}, correlation)


def update_store(event, identity, correlation):
    store_id = store_id_from(event)
    current = get_store(store_id)
    values = validate_store(parse_body(event))
    updated = {**current, **values, "updatedAt": utc_now()}
    write_store_and_audit(
        updated,
        current["updatedAt"],
        audit(identity, "UPDATE_STORE", store_id, correlation),
    )
    return response(200, {"data": updated}, correlation)


def deactivate_store(event, identity, correlation):
    store_id = store_id_from(event)
    current = get_store(store_id)
    updated = {**current, "status": "INACTIVE", "updatedAt": utc_now()}
    write_store_and_audit(
        updated,
        current["updatedAt"],
        audit(identity, "DEACTIVATE_STORE", store_id, correlation),
    )
    return response(200, {"data": updated}, correlation)


HANDLERS = {
    "CREATE": create_store,
    "LIST": list_stores,
    "GET": get_store_response,
    "UPDATE": update_store,
    "DEACTIVATE": deactivate_store,
}


def lambda_handler(event, context):
    correlation = correlation_id(event, context)
    action = None
    try:
        action = route_action(event)
        roles = (
            {"ADMINISTRADOR"}
            if action in {"CREATE", "UPDATE", "DEACTIVATE"}
            else {"ADMINISTRADOR", "OPERADOR", "CLIENTE"}
        )
        identity = require_role(event, roles)
        result = HANDLERS[action](event, identity, correlation)
        log_event(
            "info",
            "store_request_completed",
            correlation,
            action=action,
            actorId=identity["actor_id"],
            role=identity["role"],
        )
        return result
    except ApiError as exc:
        log_event(
            "warning",
            "store_request_rejected",
            correlation,
            action=action,
            statusCode=exc.status_code,
            errorCode=exc.code,
        )
        return error_response(exc, correlation)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        status = 409 if code in {"TransactionCanceledException", "ConditionalCheckFailedException"} else 500
        log_event(
            "error",
            "store_dependency_error",
            correlation,
            action=action,
            statusCode=status,
            errorCode=code,
        )
        return error_response(
            ApiError(
                status,
                "CONFLICT" if status == 409 else "INTERNAL_ERROR",
                "No se pudo completar la operación",
            ),
            correlation,
        )
    except Exception:
        log_event(
            "exception",
            "store_unexpected_error",
            correlation,
            action=action,
            statusCode=500,
            errorCode="INTERNAL_ERROR",
        )
        return error_response(
            ApiError(500, "INTERNAL_ERROR", "Error interno del servidor"),
            correlation,
        )
