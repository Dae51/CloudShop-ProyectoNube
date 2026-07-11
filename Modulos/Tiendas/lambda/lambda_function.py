import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError


STORES_TABLE = os.environ.get("STORES_TABLE", "Stores")
STATUS_INDEX = os.environ.get("STATUS_INDEX", "StatusCreatedAtIndex")

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()
dynamodb = boto3.client("dynamodb")

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
VALID_STATUSES = {"ACTIVE", "DISABLED"}
UPDATABLE_FIELDS = {"name", "description", "contactEmail", "phone", "address"}


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


def json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def response(status_code, body=None):
    payload = "" if body is None else json.dumps(body, ensure_ascii=False, default=json_default)
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


def serialize_item(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def deserialize_item(item):
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


def parse_body(event):
    raw_body = event.get("body")
    if raw_body is None:
        raise ApiError(400, "INVALID_INPUT", "El cuerpo de la solicitud es obligatorio")
    if event.get("isBase64Encoded"):
        try:
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ApiError(400, "INVALID_INPUT", "El cuerpo codificado no es valido") from exc
    try:
        body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
    except json.JSONDecodeError as exc:
        raise ApiError(400, "INVALID_JSON", "El cuerpo debe contener JSON valido") from exc
    if not isinstance(body, dict):
        raise ApiError(400, "INVALID_INPUT", "El cuerpo debe ser un objeto JSON")
    return body


def required_text(body, field, max_length=200):
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "INVALID_INPUT", f"{field} es obligatorio")
    value = value.strip()
    if len(value) > max_length:
        raise ApiError(400, "INVALID_INPUT", f"{field} supera la longitud permitida")
    return value


def optional_text(body, field, max_length=500):
    value = body.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ApiError(400, "INVALID_INPUT", f"{field} debe ser texto")
    value = value.strip()
    if not value:
        return None
    if len(value) > max_length:
        raise ApiError(400, "INVALID_INPUT", f"{field} supera la longitud permitida")
    return value


def validate_email(value):
    if not EMAIL_PATTERN.match(value):
        raise ApiError(400, "INVALID_INPUT", "contactEmail no tiene formato valido")
    return value


def validate_address(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ApiError(400, "INVALID_INPUT", "address debe ser un objeto JSON")
    allowed_fields = {"line1", "line2", "city", "state", "country", "postalCode"}
    address = {}
    for field in allowed_fields:
        if field in value:
            if not isinstance(value[field], str) or not value[field].strip():
                raise ApiError(400, "INVALID_INPUT", f"address.{field} debe ser texto")
            address[field] = value[field].strip()
    if not address:
        raise ApiError(400, "INVALID_INPUT", "address debe contener al menos un campo")
    return address


def path_store_id(event):
    store_id = (event.get("pathParameters") or {}).get("storeId")
    if not store_id:
        raise ApiError(400, "INVALID_INPUT", "storeId es obligatorio")
    return store_id


def validate_store_payload(body, partial=False):
    validated = {}

    if not partial or "name" in body:
        validated["name"] = required_text(body, "name", 160)
    if not partial or "ownerId" in body:
        if partial and "ownerId" in body:
            raise ApiError(400, "INVALID_INPUT", "ownerId no puede actualizarse")
        validated["ownerId"] = required_text(body, "ownerId", 120)
    if "description" in body:
        description = optional_text(body, "description", 1000)
        if description is not None:
            validated["description"] = description
    if not partial or "contactEmail" in body:
        validated["contactEmail"] = validate_email(required_text(body, "contactEmail", 254))
    if "phone" in body:
        phone = optional_text(body, "phone", 40)
        if phone is not None:
            validated["phone"] = phone
    if "address" in body:
        address = validate_address(body.get("address"))
        if address is not None:
            validated["address"] = address

    if partial and not any(field in validated for field in UPDATABLE_FIELDS):
        raise ApiError(400, "INVALID_INPUT", "Debe enviar al menos un campo actualizable")
    return validated


def get_store_item(store_id):
    result = dynamodb.get_item(
        TableName=STORES_TABLE,
        Key={"storeId": {"S": store_id}},
        ConsistentRead=True,
    )
    item = result.get("Item")
    if not item:
        raise ApiError(404, "STORE_NOT_FOUND", "La tienda no existe")
    return deserialize_item(item)


def create_store(event):
    body = validate_store_payload(parse_body(event))
    timestamp = utc_now()
    store = {
        "storeId": str(uuid.uuid4()),
        **body,
        "status": "ACTIVE",
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    dynamodb.put_item(
        TableName=STORES_TABLE,
        Item=serialize_item(store),
        ConditionExpression="attribute_not_exists(storeId)",
    )
    log_event("info", "store_created", storeId=store["storeId"], ownerId=store["ownerId"])
    return response(201, {"data": store})


def get_store(event):
    store_id = path_store_id(event)
    store = get_store_item(store_id)
    return response(200, {"data": store})


def list_stores(event):
    params = event.get("queryStringParameters") or {}
    status = str(params.get("status", "ACTIVE")).upper()
    if status not in VALID_STATUSES:
        raise ApiError(400, "INVALID_INPUT", "status no es valido")

    result = dynamodb.query(
        TableName=STORES_TABLE,
        IndexName=STATUS_INDEX,
        KeyConditionExpression="#status = :status",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": {"S": status}},
        ScanIndexForward=False,
    )
    items = [deserialize_item(item) for item in result.get("Items", [])]
    return response(200, {"data": items, "count": len(items)})


def update_store(event):
    store_id = path_store_id(event)
    current = get_store_item(store_id)
    if current.get("status") == "DISABLED":
        raise ApiError(409, "STORE_DISABLED", "La tienda esta deshabilitada")

    updates = validate_store_payload(parse_body(event), partial=True)
    updated = {**current, **updates, "updatedAt": utc_now()}
    dynamodb.put_item(
        TableName=STORES_TABLE,
        Item=serialize_item(updated),
        ConditionExpression="attribute_exists(storeId) AND #status = :active AND updatedAt = :previousUpdatedAt",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":active": {"S": "ACTIVE"},
            ":previousUpdatedAt": {"S": current["updatedAt"]},
        },
    )
    log_event("info", "store_updated", storeId=store_id)
    return response(200, {"data": updated})


def disable_store(event):
    store_id = path_store_id(event)
    timestamp = utc_now()
    result = dynamodb.update_item(
        TableName=STORES_TABLE,
        Key={"storeId": {"S": store_id}},
        UpdateExpression="SET #status = :disabled, disabledAt = :disabledAt, updatedAt = :updatedAt",
        ConditionExpression="attribute_exists(storeId) AND #status = :active",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":disabled": {"S": "DISABLED"},
            ":active": {"S": "ACTIVE"},
            ":disabledAt": {"S": timestamp},
            ":updatedAt": {"S": timestamp},
        },
        ReturnValues="ALL_NEW",
    )
    store = deserialize_item(result["Attributes"])
    log_event("info", "store_disabled", storeId=store_id)
    return response(200, {"data": store})


def route(event):
    method = (event.get("httpMethod") or "").upper()
    resource = event.get("resource") or ""
    routes = {
        ("POST", "/tiendas"): create_store,
        ("GET", "/tiendas"): list_stores,
        ("GET", "/tiendas/{storeId}"): get_store,
        ("PUT", "/tiendas/{storeId}"): update_store,
        ("DELETE", "/tiendas/{storeId}"): disable_store,
    }
    handler = routes.get((method, resource))
    if not handler:
        raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")
    return handler(event)


def lambda_handler(event, context):
    try:
        log_event(
            "info",
            "store_request",
            requestId=context.aws_request_id,
            method=event.get("httpMethod"),
            resource=event.get("resource"),
        )
        return route(event)
    except ApiError as exc:
        log_event(
            "warning",
            "store_request_rejected",
            requestId=context.aws_request_id,
            statusCode=exc.status_code,
            errorCode=exc.code,
        )
        return error_response(exc.status_code, exc.code, exc.message)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        log_event("exception", "store_aws_error", requestId=context.aws_request_id, errorCode=error_code)
        if error_code == "ConditionalCheckFailedException":
            return error_response(409, "STORE_CONFLICT", "La tienda no existe, esta deshabilitada o fue modificada")
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    except Exception:
        log_event("exception", "store_unexpected_error", requestId=context.aws_request_id)
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
