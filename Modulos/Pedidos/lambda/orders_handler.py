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


ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "Orders")
EVENT_BUS_NAME = os.environ.get("EVENT_BUS_NAME", "cloudshop-pedidos-bus")
USER_INDEX = os.environ.get("USER_INDEX", "UserIdCreatedAtIndex")

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()
dynamodb = boto3.client("dynamodb")
eventbridge = boto3.client("events")

VALID_STATUS = {"PENDIENTE", "CONFIRMADO", "EN_PREPARACION", "PAGADO", "ENVIADO", "ENTREGADO", "CANCELADO"}
FINAL_STATUS = {"ENTREGADO", "CANCELADO"}


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
            "Access-Control-Allow-Methods": "GET,POST,PATCH,OPTIONS",
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


def required_path(event, key):
    value = (event.get("pathParameters") or {}).get(key)
    if not value:
        raise ApiError(400, "INVALID_INPUT", f"{key} es obligatorio")
    return value


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


def validate_items(raw_items):
    if not isinstance(raw_items, list) or not raw_items:
        raise ApiError(400, "INVALID_INPUT", "items debe contener al menos un producto")
    if len(raw_items) > 24:
        raise ApiError(400, "INVALID_INPUT", "items no puede superar 24 productos por pedido")

    items = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            raise ApiError(400, "INVALID_INPUT", "Cada item debe ser un objeto JSON")
        quantity = parse_quantity(raw.get("quantity"))
        unit_price = parse_money(raw.get("unitPrice"), "unitPrice")
        item = {
            "productId": required_text(raw, "productId"),
            "quantity": quantity,
            "unitPrice": unit_price,
            "subtotal": unit_price * quantity,
        }
        if raw.get("productName"):
            item["productName"] = str(raw["productName"])
        if raw.get("storeId"):
            item["storeId"] = str(raw["storeId"])
        items.append(item)
    return items


def get_order(order_id):
    result = dynamodb.get_item(TableName=ORDERS_TABLE, Key={"orderId": {"S": order_id}}, ConsistentRead=True)
    item = result.get("Item")
    if not item:
        raise ApiError(404, "ORDER_NOT_FOUND", "El pedido no existe")
    return deserialize_item(item)


def publish_order_created(order):
    detail = {
        "orderId": order["orderId"],
        "userId": order["userId"],
        "customerEmail": order.get("customerEmail"),
        "status": order["status"],
        "total": order["total"],
        "items": order["items"],
        "createdAt": order["createdAt"],
    }
    result = eventbridge.put_events(
        Entries=[
            {
                "Source": "cloudshop.pedidos",
                "DetailType": "PedidoCreado",
                "Detail": json.dumps(detail, ensure_ascii=False, default=json_default),
                "EventBusName": EVENT_BUS_NAME,
            }
        ]
    )
    if result.get("FailedEntryCount", 0) > 0:
        raise ApiError(500, "EVENT_PUBLICATION_FAILED", "No se pudo publicar el evento del pedido")


def create_order(event):
    body = parse_body(event)
    items = validate_items(body.get("items"))
    timestamp = utc_now()
    order = {
        "orderId": str(uuid.uuid4()),
        "userId": required_text(body, "userId"),
        "status": "PENDIENTE",
        "items": items,
        "total": sum(item["subtotal"] for item in items),
        "currency": str(body.get("currency", "USD")),
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "inventoryStatus": "PENDIENTE",
        "eventPublicationStatus": "PENDIENTE",
    }
    if body.get("customerEmail"):
        order["customerEmail"] = str(body["customerEmail"])
    if body.get("shippingAddress"):
        order["shippingAddress"] = body["shippingAddress"]

    dynamodb.put_item(TableName=ORDERS_TABLE, Item=serialize_item(order), ConditionExpression="attribute_not_exists(orderId)")
    try:
        publish_order_created(order)
        order["eventPublicationStatus"] = "PUBLICADO"
        dynamodb.update_item(
            TableName=ORDERS_TABLE,
            Key={"orderId": {"S": order["orderId"]}},
            UpdateExpression="SET eventPublicationStatus = :status, updatedAt = :updatedAt",
            ExpressionAttributeValues={":status": {"S": "PUBLICADO"}, ":updatedAt": {"S": utc_now()}},
        )
    except ApiError:
        dynamodb.update_item(
            TableName=ORDERS_TABLE,
            Key={"orderId": {"S": order["orderId"]}},
            UpdateExpression="SET eventPublicationStatus = :status, updatedAt = :updatedAt",
            ExpressionAttributeValues={":status": {"S": "FALLIDO"}, ":updatedAt": {"S": utc_now()}},
        )
        raise

    log_event("info", "order_created", orderId=order["orderId"], userId=order["userId"])
    return response(201, {"data": order})


def get_order_response(event):
    return response(200, {"data": get_order(required_path(event, "orderId"))})


def list_user_orders(event):
    user_id = required_path(event, "userId")
    result = dynamodb.query(
        TableName=ORDERS_TABLE,
        IndexName=USER_INDEX,
        KeyConditionExpression="userId = :userId",
        ExpressionAttributeValues={":userId": {"S": user_id}},
        ScanIndexForward=False,
    )
    items = [deserialize_item(item) for item in result.get("Items", [])]
    return response(200, {"data": items, "count": len(items)})


def update_order(event):
    order_id = required_path(event, "orderId")
    current = get_order(order_id)
    if current.get("status") in FINAL_STATUS:
        raise ApiError(409, "ORDER_FINALIZED", "El pedido ya se encuentra en estado final")
    body = parse_body(event)
    status = required_text(body, "status").upper()
    if status not in VALID_STATUS:
        raise ApiError(400, "INVALID_INPUT", "status no es valido")
    result = dynamodb.update_item(
        TableName=ORDERS_TABLE,
        Key={"orderId": {"S": order_id}},
        UpdateExpression="SET #status = :status, updatedAt = :updatedAt",
        ConditionExpression="attribute_exists(orderId) AND #status = :current",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={":status": {"S": status}, ":updatedAt": {"S": utc_now()}, ":current": {"S": current["status"]}},
        ReturnValues="ALL_NEW",
    )
    updated = deserialize_item(result["Attributes"])
    log_event("info", "order_updated", orderId=order_id, status=status)
    return response(200, {"data": updated})


def route(event):
    method = (event.get("httpMethod") or "").upper()
    resource = event.get("resource") or ""
    routes = {
        ("POST", "/pedidos"): create_order,
        ("GET", "/pedidos/{orderId}"): get_order_response,
        ("PATCH", "/pedidos/{orderId}"): update_order,
        ("GET", "/usuarios/{userId}/pedidos"): list_user_orders,
    }
    handler = routes.get((method, resource))
    if not handler:
        raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")
    return handler(event)


def lambda_handler(event, context):
    try:
        log_event("info", "order_request", requestId=context.aws_request_id, method=event.get("httpMethod"), resource=event.get("resource"))
        return route(event)
    except ApiError as exc:
        log_event("warning", "order_request_rejected", requestId=context.aws_request_id, statusCode=exc.status_code, errorCode=exc.code)
        return error_response(exc.status_code, exc.code, exc.message)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        log_event("exception", "order_aws_error", requestId=context.aws_request_id, errorCode=error_code)
        if error_code in {"ConditionalCheckFailedException", "TransactionCanceledException"}:
            return error_response(409, "CONFLICT", "El pedido no pudo modificarse por conflicto de estado")
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    except Exception:
        log_event("exception", "order_unexpected_error", requestId=context.aws_request_id)
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
