import base64
import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError


CART_TABLE = os.environ.get("CART_TABLE", "CartItems")
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


def required_path(event, key):
    value = (event.get("pathParameters") or {}).get(key)
    if not value:
        raise ApiError(400, "INVALID_INPUT", f"{key} es obligatorio")
    return value


def required_text(body, field):
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "INVALID_INPUT", f"{field} es obligatorio")
    return value.strip()


def parse_quantity(value):
    if isinstance(value, bool):
        raise ApiError(400, "INVALID_INPUT", "quantity debe ser un entero mayor que 0")
    try:
        quantity = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "INVALID_INPUT", "quantity debe ser un entero mayor que 0") from exc
    if quantity <= 0 or (isinstance(value, float) and not value.is_integer()):
        raise ApiError(400, "INVALID_INPUT", "quantity debe ser un entero mayor que 0")
    return quantity


def parse_money(value, field):
    if isinstance(value, bool):
        raise ApiError(400, "INVALID_INPUT", f"{field} debe ser numerico")
    try:
        amount = Decimal(str(value))
    except Exception as exc:
        raise ApiError(400, "INVALID_INPUT", f"{field} debe ser numerico") from exc
    if not amount.is_finite() or amount < 0:
        raise ApiError(400, "INVALID_INPUT", f"{field} no es valido")
    return amount


def cart_key(user_id, product_id):
    return {"userId": {"S": user_id}, "productId": {"S": product_id}}


def get_cart_item(user_id, product_id):
    result = dynamodb.get_item(TableName=CART_TABLE, Key=cart_key(user_id, product_id), ConsistentRead=True)
    item = result.get("Item")
    if not item:
        raise ApiError(404, "CART_ITEM_NOT_FOUND", "El producto no existe en el carrito")
    return deserialize_item(item)


def add_item(event):
    user_id = required_path(event, "userId")
    body = parse_body(event)
    product_id = required_text(body, "productId")
    quantity = parse_quantity(body.get("quantity"))
    unit_price = parse_money(body.get("unitPrice"), "unitPrice")
    timestamp = utc_now()
    item = {
        "userId": user_id,
        "productId": product_id,
        "quantity": quantity,
        "unitPrice": unit_price,
        "productName": required_text(body, "productName"),
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    if body.get("storeId"):
        item["storeId"] = str(body["storeId"])
    dynamodb.put_item(TableName=CART_TABLE, Item=serialize_item(item))
    log_event("info", "cart_item_added", userId=user_id, productId=product_id)
    return response(201, {"data": item})


def get_cart(event):
    user_id = required_path(event, "userId")
    result = dynamodb.query(
        TableName=CART_TABLE,
        KeyConditionExpression="userId = :userId",
        ExpressionAttributeValues={":userId": {"S": user_id}},
    )
    items = [deserialize_item(item) for item in result.get("Items", [])]
    total = sum(item["unitPrice"] * item["quantity"] for item in items)
    return response(200, {"data": {"userId": user_id, "items": items, "total": total, "count": len(items)}})


def get_item(event):
    return response(200, {"data": get_cart_item(required_path(event, "userId"), required_path(event, "productId"))})


def update_item(event):
    user_id = required_path(event, "userId")
    product_id = required_path(event, "productId")
    body = parse_body(event)
    if "quantity" not in body:
        raise ApiError(400, "INVALID_INPUT", "quantity es obligatorio")
    result = dynamodb.update_item(
        TableName=CART_TABLE,
        Key=cart_key(user_id, product_id),
        UpdateExpression="SET quantity = :quantity, updatedAt = :updatedAt",
        ConditionExpression="attribute_exists(userId) AND attribute_exists(productId)",
        ExpressionAttributeValues={":quantity": {"N": str(parse_quantity(body["quantity"]))}, ":updatedAt": {"S": utc_now()}},
        ReturnValues="ALL_NEW",
    )
    item = deserialize_item(result["Attributes"])
    log_event("info", "cart_item_updated", userId=user_id, productId=product_id)
    return response(200, {"data": item})


def delete_item(event):
    user_id = required_path(event, "userId")
    product_id = required_path(event, "productId")
    dynamodb.delete_item(
        TableName=CART_TABLE,
        Key=cart_key(user_id, product_id),
        ConditionExpression="attribute_exists(userId) AND attribute_exists(productId)",
    )
    log_event("info", "cart_item_deleted", userId=user_id, productId=product_id)
    return response(204)


def clear_cart(event):
    user_id = required_path(event, "userId")
    result = dynamodb.query(
        TableName=CART_TABLE,
        KeyConditionExpression="userId = :userId",
        ExpressionAttributeValues={":userId": {"S": user_id}},
        ProjectionExpression="userId, productId",
    )
    for item in result.get("Items", []):
        dynamodb.delete_item(TableName=CART_TABLE, Key={"userId": item["userId"], "productId": item["productId"]})
    log_event("info", "cart_cleared", userId=user_id, deleted=len(result.get("Items", [])))
    return response(204)


def route(event):
    method = (event.get("httpMethod") or "").upper()
    resource = event.get("resource") or ""
    routes = {
        ("POST", "/carritos/{userId}/items"): add_item,
        ("GET", "/carritos/{userId}"): get_cart,
        ("GET", "/carritos/{userId}/items/{productId}"): get_item,
        ("PATCH", "/carritos/{userId}/items/{productId}"): update_item,
        ("DELETE", "/carritos/{userId}/items/{productId}"): delete_item,
        ("DELETE", "/carritos/{userId}"): clear_cart,
    }
    handler = routes.get((method, resource))
    if not handler:
        raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")
    return handler(event)


def lambda_handler(event, context):
    try:
        log_event("info", "cart_request", requestId=context.aws_request_id, method=event.get("httpMethod"), resource=event.get("resource"))
        return route(event)
    except ApiError as exc:
        log_event("warning", "cart_request_rejected", requestId=context.aws_request_id, statusCode=exc.status_code, errorCode=exc.code)
        return error_response(exc.status_code, exc.code, exc.message)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        log_event("exception", "cart_aws_error", requestId=context.aws_request_id, errorCode=error_code)
        if error_code == "ConditionalCheckFailedException":
            return error_response(404, "CART_ITEM_NOT_FOUND", "El producto no existe en el carrito")
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    except Exception:
        log_event("exception", "cart_unexpected_error", requestId=context.aws_request_id)
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
