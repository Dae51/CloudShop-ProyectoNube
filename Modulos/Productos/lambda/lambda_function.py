import base64
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError


PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "Products")
AUDIT_TABLE = os.environ.get("AUDIT_TABLE", "ProductAudit")
STORE_INDEX = os.environ.get("STORE_INDEX", "StoreIdCreatedAtIndex")

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
            "Access-Control-Allow-Methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
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
        raw_body = base64.b64decode(raw_body).decode("utf-8")
    try:
        body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
    except json.JSONDecodeError as exc:
        raise ApiError(400, "INVALID_JSON", "El cuerpo debe contener JSON valido") from exc
    if not isinstance(body, dict):
        raise ApiError(400, "INVALID_INPUT", "El cuerpo debe ser un objeto JSON")
    return body


def required_text(body, field):
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "INVALID_INPUT", f"{field} es obligatorio")
    return value.strip()


def parse_decimal(value, field, minimum=Decimal("0")):
    if isinstance(value, bool):
        raise ApiError(400, "INVALID_INPUT", f"{field} debe ser numerico")
    try:
        parsed = Decimal(str(value))
    except Exception as exc:
        raise ApiError(400, "INVALID_INPUT", f"{field} debe ser numerico") from exc
    if not parsed.is_finite() or parsed < minimum:
        raise ApiError(400, "INVALID_INPUT", f"{field} no es valido")
    return parsed


def parse_inventory(value):
    if isinstance(value, bool):
        raise ApiError(400, "INVALID_INPUT", "inventory debe ser un entero mayor o igual que 0")
    try:
        inventory = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "INVALID_INPUT", "inventory debe ser un entero mayor o igual que 0") from exc
    if inventory < 0 or (isinstance(value, float) and not value.is_integer()):
        raise ApiError(400, "INVALID_INPUT", "inventory debe ser un entero mayor o igual que 0")
    return inventory


def validate_product(body):
    return {
        "code": required_text(body, "code"),
        "name": required_text(body, "name"),
        "description": required_text(body, "description"),
        "category": required_text(body, "category"),
        "price": parse_decimal(body.get("price"), "price", Decimal("0.01")),
        "inventory": parse_inventory(body.get("inventory")),
        "storeId": required_text(body, "storeId"),
    }


def audit(action, product_id, result="EXITOSO"):
    item = {
        "auditId": str(uuid.uuid4()),
        "accion": action,
        "resourceType": "PRODUCT",
        "resourceId": product_id,
        "fecha": utc_now(),
        "resultado": result,
    }
    dynamodb.put_item(TableName=AUDIT_TABLE, Item=serialize_item(item))


def get_product(product_id):
    result = dynamodb.get_item(TableName=PRODUCTS_TABLE, Key={"productId": {"S": product_id}}, ConsistentRead=True)
    item = result.get("Item")
    if not item:
        raise ApiError(404, "PRODUCT_NOT_FOUND", "El producto no existe")
    product = deserialize_item(item)
    if product.get("status") == "DELETED":
        raise ApiError(404, "PRODUCT_NOT_FOUND", "El producto no existe")
    return product


def create_product(event):
    body = validate_product(parse_body(event))
    timestamp = utc_now()
    product = {"productId": str(uuid.uuid4()), **body, "status": "ACTIVE", "createdAt": timestamp, "updatedAt": timestamp}
    dynamodb.put_item(TableName=PRODUCTS_TABLE, Item=serialize_item(product), ConditionExpression="attribute_not_exists(productId)")
    audit("CREATE_PRODUCT", product["productId"])
    log_event("info", "product_created", productId=product["productId"])
    return response(201, {"data": product})


def list_products(_event):
    result = dynamodb.scan(
        TableName=PRODUCTS_TABLE,
        FilterExpression="#status = :active",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":active": {"S": "ACTIVE"}},
    )
    items = [deserialize_item(item) for item in result.get("Items", [])]
    return response(200, {"data": items, "count": len(items)})


def get_product_response(event):
    product_id = (event.get("pathParameters") or {}).get("productId")
    if not product_id:
        raise ApiError(400, "INVALID_INPUT", "productId es obligatorio")
    return response(200, {"data": get_product(product_id)})


def list_by_store(event):
    store_id = (event.get("pathParameters") or {}).get("storeId")
    if not store_id:
        raise ApiError(400, "INVALID_INPUT", "storeId es obligatorio")
    result = dynamodb.query(
        TableName=PRODUCTS_TABLE,
        IndexName=STORE_INDEX,
        KeyConditionExpression="storeId = :storeId",
        FilterExpression="#status = :active",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":storeId": {"S": store_id}, ":active": {"S": "ACTIVE"}},
    )
    items = [deserialize_item(item) for item in result.get("Items", [])]
    return response(200, {"data": items, "count": len(items)})


def update_product(event):
    product_id = (event.get("pathParameters") or {}).get("productId")
    current = get_product(product_id)
    updated = {**current, **validate_product(parse_body(event)), "updatedAt": utc_now()}
    dynamodb.put_item(
        TableName=PRODUCTS_TABLE,
        Item=serialize_item(updated),
        ConditionExpression="attribute_exists(productId) AND updatedAt = :updatedAt",
        ExpressionAttributeValues={":updatedAt": {"S": current["updatedAt"]}},
    )
    audit("UPDATE_PRODUCT", product_id)
    return response(200, {"data": updated})


def update_inventory(event):
    product_id = (event.get("pathParameters") or {}).get("productId")
    body = parse_body(event)
    if "inventory" not in body:
        raise ApiError(400, "INVALID_INPUT", "inventory es obligatorio")
    result = dynamodb.update_item(
        TableName=PRODUCTS_TABLE,
        Key={"productId": {"S": product_id}},
        UpdateExpression="SET inventory = :inventory, updatedAt = :updatedAt",
        ConditionExpression="attribute_exists(productId) AND #status = :active",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":inventory": {"N": str(parse_inventory(body["inventory"]))}, ":updatedAt": {"S": utc_now()}, ":active": {"S": "ACTIVE"}},
        ReturnValues="ALL_NEW",
    )
    audit("UPDATE_PRODUCT_INVENTORY", product_id)
    return response(200, {"data": deserialize_item(result["Attributes"])})


def delete_product(event):
    product_id = (event.get("pathParameters") or {}).get("productId")
    current = get_product(product_id)
    current.update({"status": "DELETED", "updatedAt": utc_now()})
    dynamodb.put_item(TableName=PRODUCTS_TABLE, Item=serialize_item(current))
    audit("DELETE_PRODUCT", product_id)
    return response(200, {"data": current})


def route(event):
    method = (event.get("httpMethod") or "").upper()
    resource = event.get("resource") or ""
    routes = {
        ("POST", "/productos"): create_product,
        ("GET", "/productos"): list_products,
        ("GET", "/productos/{productId}"): get_product_response,
        ("PUT", "/productos/{productId}"): update_product,
        ("DELETE", "/productos/{productId}"): delete_product,
        ("PATCH", "/productos/{productId}/inventario"): update_inventory,
        ("GET", "/tiendas/{storeId}/productos"): list_by_store,
    }
    handler = routes.get((method, resource))
    if not handler:
        raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")
    return handler(event)


def lambda_handler(event, context):
    try:
        log_event("info", "product_request", requestId=context.aws_request_id, method=event.get("httpMethod"), resource=event.get("resource"))
        return route(event)
    except ApiError as exc:
        log_event("warning", "product_request_rejected", requestId=context.aws_request_id, statusCode=exc.status_code, errorCode=exc.code)
        return error_response(exc.status_code, exc.code, exc.message)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        log_event("exception", "product_aws_error", requestId=context.aws_request_id, errorCode=error_code)
        if error_code in {"ConditionalCheckFailedException", "TransactionCanceledException"}:
            return error_response(409, "CONFLICT", "El producto no pudo modificarse por conflicto de estado")
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    except Exception:
        log_event("exception", "product_unexpected_error", requestId=context.aws_request_id)
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
