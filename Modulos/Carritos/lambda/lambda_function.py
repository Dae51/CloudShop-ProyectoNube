import os

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from cloudshop_common import (
    ApiError,
    correlation_id,
    error_response,
    log_event,
    parse_body,
    require_role,
    response,
    utc_now,
)


CARTS_TABLE = os.environ["CARTS_TABLE"]
PRODUCTS_TABLE = os.environ["PRODUCTS_TABLE"]
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
        ("GET", "/carritos/mio"): "GET",
        ("DELETE", "/carritos/mio"): "CLEAR",
        ("POST", "/carritos/mio/items"): "ADD",
        ("PATCH", "/carritos/mio/items/{productId}"): "UPDATE",
        ("DELETE", "/carritos/mio/items/{productId}"): "REMOVE",
    }.get(key)
    if not action:
        raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")
    return action


def parse_quantity(value):
    if isinstance(value, bool):
        raise ApiError(400, "INVALID_INPUT", "quantity debe ser un entero entre 1 y 99")
    try:
        quantity = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "INVALID_INPUT", "quantity debe ser un entero entre 1 y 99") from exc
    if quantity < 1 or quantity > 99 or str(quantity) != str(value).strip():
        raise ApiError(400, "INVALID_INPUT", "quantity debe ser un entero entre 1 y 99")
    return quantity


def get_cart(customer_id):
    result = client().get_item(
        TableName=CARTS_TABLE,
        Key={"customerId": {"S": customer_id}},
        ConsistentRead=True,
    )
    if "Item" not in result:
        return {
            "customerId": customer_id,
            "items": [],
            "version": 0,
            "updatedAt": utc_now(),
        }
    return deserialize(result["Item"])


def active_product(product_id, quantity):
    result = client().get_item(
        TableName=PRODUCTS_TABLE,
        Key={"productId": {"S": product_id}},
        ConsistentRead=True,
    )
    if "Item" not in result:
        raise ApiError(404, "PRODUCT_NOT_FOUND", "El producto no existe")
    product = deserialize(result["Item"])
    if product.get("status") != "ACTIVE":
        raise ApiError(404, "PRODUCT_NOT_FOUND", "El producto no existe")
    if int(product.get("inventory", 0)) < quantity:
        raise ApiError(409, "INSUFFICIENT_STOCK", "Inventario insuficiente")
    return product


def save_cart(cart, previous_version):
    request = {
        "TableName": CARTS_TABLE,
        "Item": serialize(cart),
    }
    if previous_version == 0:
        request["ConditionExpression"] = "attribute_not_exists(customerId)"
    else:
        request["ConditionExpression"] = "#version = :previous"
        request["ExpressionAttributeNames"] = {"#version": "version"}
        request["ExpressionAttributeValues"] = {
            ":previous": {"N": str(previous_version)}
        }
    client().put_item(**request)


def get_cart_response(event, identity, correlation):
    return response(200, {"data": get_cart(identity["customer_id"])}, correlation)


def add_item(event, identity, correlation):
    body = parse_body(event)
    if set(body) != {"productId", "quantity"} or not isinstance(body["productId"], str):
        raise ApiError(400, "INVALID_INPUT", "productId y quantity son obligatorios")
    product_id = body["productId"].strip()
    quantity = parse_quantity(body["quantity"])
    active_product(product_id, quantity)
    current = get_cart(identity["customer_id"])
    items = list(current["items"])
    existing = next((item for item in items if item["productId"] == product_id), None)
    if existing:
        new_quantity = existing["quantity"] + quantity
        if new_quantity > 99:
            raise ApiError(400, "INVALID_INPUT", "quantity total no puede exceder 99")
        active_product(product_id, new_quantity)
        existing["quantity"] = new_quantity
    else:
        if len(items) >= 20:
            raise ApiError(400, "INVALID_INPUT", "El carrito admite máximo 20 productos")
        items.append({"productId": product_id, "quantity": quantity})
    updated = {
        **current,
        "items": items,
        "version": current["version"] + 1,
        "updatedAt": utc_now(),
    }
    save_cart(updated, current["version"])
    return response(200, {"data": updated}, correlation)


def product_id_from(event):
    value = (event.get("pathParameters") or {}).get("productId")
    if not value:
        raise ApiError(400, "INVALID_INPUT", "productId es obligatorio")
    return value


def update_item(event, identity, correlation):
    product_id = product_id_from(event)
    body = parse_body(event)
    if set(body) != {"quantity"}:
        raise ApiError(400, "INVALID_INPUT", "quantity es obligatorio")
    quantity = parse_quantity(body["quantity"])
    active_product(product_id, quantity)
    current = get_cart(identity["customer_id"])
    if not any(item["productId"] == product_id for item in current["items"]):
        raise ApiError(404, "CART_ITEM_NOT_FOUND", "El producto no está en el carrito")
    items = [
        {"productId": item["productId"], "quantity": quantity}
        if item["productId"] == product_id
        else item
        for item in current["items"]
    ]
    updated = {
        **current,
        "items": items,
        "version": current["version"] + 1,
        "updatedAt": utc_now(),
    }
    save_cart(updated, current["version"])
    return response(200, {"data": updated}, correlation)


def remove_item(event, identity, correlation):
    product_id = product_id_from(event)
    current = get_cart(identity["customer_id"])
    items = [item for item in current["items"] if item["productId"] != product_id]
    if len(items) == len(current["items"]):
        raise ApiError(404, "CART_ITEM_NOT_FOUND", "El producto no está en el carrito")
    updated = {
        **current,
        "items": items,
        "version": current["version"] + 1,
        "updatedAt": utc_now(),
    }
    save_cart(updated, current["version"])
    return response(200, {"data": updated}, correlation)


def clear_cart(event, identity, correlation):
    client().delete_item(
        TableName=CARTS_TABLE,
        Key={"customerId": {"S": identity["customer_id"]}},
    )
    return response(204, correlation=correlation)


HANDLERS = {
    "GET": get_cart_response,
    "ADD": add_item,
    "UPDATE": update_item,
    "REMOVE": remove_item,
    "CLEAR": clear_cart,
}


def lambda_handler(event, context):
    correlation = correlation_id(event, context)
    action = None
    try:
        action = route_action(event)
        identity = require_role(event, {"CLIENTE"})
        result = HANDLERS[action](event, identity, correlation)
        log_event(
            "info",
            "cart_request_completed",
            correlation,
            action=action,
            customerId=identity["customer_id"],
        )
        return result
    except ApiError as exc:
        return error_response(exc, correlation)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        status = 409 if code == "ConditionalCheckFailedException" else 500
        return error_response(
            ApiError(
                status,
                "CONCURRENT_MODIFICATION" if status == 409 else "INTERNAL_ERROR",
                "El carrito cambió; recargue e intente nuevamente"
                if status == 409
                else "Error interno del servidor",
            ),
            correlation,
        )
    except Exception:
        log_event("exception", "cart_unexpected_error", correlation, action=action)
        return error_response(
            ApiError(500, "INTERNAL_ERROR", "Error interno del servidor"),
            correlation,
        )
