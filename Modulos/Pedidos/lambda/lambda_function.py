import os
import time
import uuid
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError

from cloudshop_common import (
    ApiError,
    correlation_id,
    error_response,
    idempotency_key,
    log_event,
    parse_body,
    require_role,
    response,
    utc_now,
)


ORDERS_TABLE = os.environ["ORDERS_TABLE"]
CARTS_TABLE = os.environ["CARTS_TABLE"]
PRODUCTS_TABLE = os.environ["PRODUCTS_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
OUTBOX_TABLE = os.environ["OUTBOX_TABLE"]
IDEMPOTENCY_TABLE = os.environ["IDEMPOTENCY_TABLE"]
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()
_dynamodb = None

ORDER_STATES = {
    "PENDIENTE",
    "CONFIRMADO",
    "EN_PREPARACION",
    "ENVIADO",
    "ENTREGADO",
    "CANCELADO",
}
NEXT_STATES = {
    "PENDIENTE": {"CONFIRMADO"},
    "CONFIRMADO": {"EN_PREPARACION"},
    "EN_PREPARACION": {"ENVIADO"},
    "ENVIADO": {"ENTREGADO"},
    "ENTREGADO": set(),
    "CANCELADO": set(),
}
CANCELLABLE = {"PENDIENTE", "CONFIRMADO"}


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
        ("POST", "/pedidos"): "CREATE",
        ("GET", "/pedidos"): "LIST",
        ("GET", "/pedidos/mios"): "LIST_MINE",
        ("GET", "/pedidos/{orderId}"): "GET",
        ("PATCH", "/pedidos/{orderId}/estado"): "UPDATE_STATUS",
        ("POST", "/pedidos/{orderId}/cancelacion"): "CANCEL",
    }.get(key)
    if not action:
        raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")
    return action


def order_id_from(event):
    value = (event.get("pathParameters") or {}).get("orderId")
    if not value:
        raise ApiError(400, "INVALID_INPUT", "orderId es obligatorio")
    return value


def get_item(table, key_name, key_value):
    result = client().get_item(
        TableName=table,
        Key={key_name: {"S": key_value}},
        ConsistentRead=True,
    )
    return deserialize(result["Item"]) if "Item" in result else None


def get_order(order_id):
    order = get_item(ORDERS_TABLE, "orderId", order_id)
    if not order:
        raise ApiError(404, "ORDER_NOT_FOUND", "El pedido no existe")
    return order


def audit(identity, action, order_id, correlation):
    timestamp = utc_now()
    return {
        "auditId": str(uuid.uuid4()),
        "actorId": identity["actor_id"],
        "action": action,
        "resourceType": "ORDER",
        "resourceId": order_id,
        "resourceKey": f"ORDER#{order_id}",
        "occurredAt": timestamp,
        "result": "EXITOSO",
        "correlationId": correlation,
    }


def domain_event(event_type, order, identity, correlation):
    timestamp = utc_now()
    event_id = str(uuid.uuid4())
    payload = {
        "version": 1,
        "eventId": event_id,
        "eventType": event_type,
        "occurredAt": timestamp,
        "correlationId": correlation,
        "actorId": identity["actor_id"],
        "orderId": order["orderId"],
        "customerId": order["customerId"],
        "status": order["status"],
        "total": order["total"],
    }
    outbox = {
        "eventId": event_id,
        "status": "PENDING",
        "occurredAt": timestamp,
        "payload": payload,
        "expiresAt": int(time.time()) + 30 * 24 * 3600,
    }
    return payload, outbox


def command_key(scope, key):
    return f"{scope}#{key}"


def transaction_token(scope, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, command_key(scope, key)))


def idempotency_item(scope, key, order_id, operation):
    return {
        "idempotencyKey": command_key(scope, key),
        "orderId": order_id,
        "operation": operation,
        "createdAt": utc_now(),
        "expiresAt": int(time.time()) + 24 * 3600,
    }


def replay(scope, key):
    record = get_item(IDEMPOTENCY_TABLE, "idempotencyKey", command_key(scope, key))
    return get_order(record["orderId"]) if record else None


def product_for_checkout(product_id, quantity):
    product = get_item(PRODUCTS_TABLE, "productId", product_id)
    if not product or product.get("status") != "ACTIVE":
        raise ApiError(404, "PRODUCT_NOT_FOUND", "Un producto del carrito no existe")
    if int(product.get("inventory", 0)) < quantity:
        raise ApiError(409, "INSUFFICIENT_STOCK", "Inventario insuficiente")
    return product


def checkout(event, identity, correlation):
    key = idempotency_key(event)
    scope = f"CHECKOUT#{identity['customer_id']}"
    previous = replay(scope, key)
    if previous:
        result = response(200, {"data": previous}, correlation)
        result["headers"]["Idempotent-Replayed"] = "true"
        return result

    cart = get_item(CARTS_TABLE, "customerId", identity["customer_id"])
    if not cart or not cart.get("items"):
        raise ApiError(400, "EMPTY_CART", "El carrito está vacío")
    if len(cart["items"]) > 20:
        raise ApiError(400, "INVALID_INPUT", "El carrito excede 20 productos")

    order_items = []
    total = Decimal("0")
    for cart_item in cart["items"]:
        quantity = int(cart_item["quantity"])
        product = product_for_checkout(cart_item["productId"], quantity)
        unit_price = Decimal(str(product["price"]))
        subtotal = unit_price * quantity
        total += subtotal
        order_items.append(
            {
                "productId": product["productId"],
                "storeId": product["storeId"],
                "name": product["name"],
                "unitPrice": unit_price,
                "quantity": quantity,
                "subtotal": subtotal,
            }
        )

    timestamp = utc_now()
    order_id = str(uuid.uuid4())
    order = {
        "orderId": order_id,
        "customerId": identity["customer_id"],
        "actorId": identity["actor_id"],
        "status": "PENDIENTE",
        "items": order_items,
        "total": total,
        "correlationId": correlation,
        "idempotencyKey": key,
        "inventoryRestored": False,
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    _, outbox = domain_event("OrderCreated", order, identity, correlation)
    transaction = []
    for item in order_items:
        transaction.append(
            {
                "Update": {
                    "TableName": PRODUCTS_TABLE,
                    "Key": {"productId": {"S": item["productId"]}},
                    "UpdateExpression": "SET inventory = inventory - :quantity, updatedAt = :updated",
                    "ConditionExpression": "#status = :active AND inventory >= :quantity",
                    "ExpressionAttributeNames": {"#status": "status"},
                    "ExpressionAttributeValues": {
                        ":quantity": {"N": str(item["quantity"])},
                        ":updated": {"S": timestamp},
                        ":active": {"S": "ACTIVE"},
                    },
                }
            }
        )
    transaction.extend(
        [
            {
                "Put": {
                    "TableName": ORDERS_TABLE,
                    "Item": serialize(order),
                    "ConditionExpression": "attribute_not_exists(orderId)",
                }
            },
            {
                "Put": {
                    "TableName": AUDIT_TABLE,
                    "Item": serialize(
                        audit(identity, "CREATE_ORDER", order_id, correlation)
                    ),
                }
            },
            {"Put": {"TableName": OUTBOX_TABLE, "Item": serialize(outbox)}},
            {
                "Put": {
                    "TableName": IDEMPOTENCY_TABLE,
                    "Item": serialize(
                        idempotency_item(scope, key, order_id, "CREATE_ORDER")
                    ),
                    "ConditionExpression": "attribute_not_exists(idempotencyKey)",
                }
            },
            {
                "Delete": {
                    "TableName": CARTS_TABLE,
                    "Key": {"customerId": {"S": identity["customer_id"]}},
                    "ConditionExpression": "#version = :version",
                    "ExpressionAttributeNames": {"#version": "version"},
                    "ExpressionAttributeValues": {
                        ":version": {"N": str(cart["version"])}
                    },
                }
            },
        ]
    )
    try:
        client().transact_write_items(
            TransactItems=transaction,
            ClientRequestToken=transaction_token(scope, key),
        )
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") == "TransactionCanceledException":
            previous = replay(scope, key)
            if previous:
                result = response(200, {"data": previous}, correlation)
                result["headers"]["Idempotent-Replayed"] = "true"
                return result
            raise ApiError(
                409,
                "INSUFFICIENT_STOCK",
                "El stock o el carrito cambió durante el checkout",
            ) from exc
        raise
    return response(201, {"data": order}, correlation)


def list_orders(event, identity, correlation):
    items = [
        deserialize(item)
        for item in client().scan(TableName=ORDERS_TABLE).get("Items", [])
    ]
    return response(200, {"data": items}, correlation)


def list_mine(event, identity, correlation):
    result = client().query(
        TableName=ORDERS_TABLE,
        IndexName="CustomerCreatedAtIndex",
        KeyConditionExpression="customerId = :customer",
        ExpressionAttributeValues={
            ":customer": {"S": identity["customer_id"]}
        },
        ScanIndexForward=False,
    )
    return response(
        200,
        {"data": [deserialize(item) for item in result.get("Items", [])]},
        correlation,
    )


def get_order_response(event, identity, correlation):
    order = get_order(order_id_from(event))
    if identity["role"] == "CLIENTE" and order["customerId"] != identity["customer_id"]:
        raise ApiError(403, "FORBIDDEN", "Solo puede consultar sus pedidos")
    return response(200, {"data": order}, correlation)


def transition_allowed(current, target):
    return target in NEXT_STATES.get(current, set())


def update_status(event, identity, correlation):
    order_id = order_id_from(event)
    key = idempotency_key(event)
    scope = f"STATUS#{order_id}"
    previous = replay(scope, key)
    if previous:
        return response(200, {"data": previous}, correlation)
    body = parse_body(event)
    if set(body) != {"status"} or body["status"] not in ORDER_STATES:
        raise ApiError(400, "INVALID_INPUT", "status no es válido")
    target = body["status"]
    order = get_order(order_id)
    if not transition_allowed(order["status"], target):
        raise ApiError(409, "INVALID_TRANSITION", "Transición de estado no permitida")
    updated = {**order, "status": target, "updatedAt": utc_now()}
    _, outbox = domain_event("OrderStatusChanged", updated, identity, correlation)
    client().transact_write_items(
        TransactItems=[
            {
                "Put": {
                    "TableName": ORDERS_TABLE,
                    "Item": serialize(updated),
                    "ConditionExpression": "#status = :previous AND updatedAt = :updated",
                    "ExpressionAttributeNames": {"#status": "status"},
                    "ExpressionAttributeValues": {
                        ":previous": {"S": order["status"]},
                        ":updated": {"S": order["updatedAt"]},
                    },
                }
            },
            {
                "Put": {
                    "TableName": AUDIT_TABLE,
                    "Item": serialize(
                        audit(identity, "UPDATE_ORDER_STATUS", order_id, correlation)
                    ),
                }
            },
            {"Put": {"TableName": OUTBOX_TABLE, "Item": serialize(outbox)}},
            {
                "Put": {
                    "TableName": IDEMPOTENCY_TABLE,
                    "Item": serialize(
                        idempotency_item(scope, key, order_id, "UPDATE_ORDER_STATUS")
                    ),
                    "ConditionExpression": "attribute_not_exists(idempotencyKey)",
                }
            },
        ],
        ClientRequestToken=transaction_token(scope, key),
    )
    return response(200, {"data": updated}, correlation)


def cancel_order(event, identity, correlation):
    order_id = order_id_from(event)
    key = idempotency_key(event)
    scope = f"CANCEL#{order_id}"
    previous = replay(scope, key)
    if previous:
        return response(200, {"data": previous}, correlation)
    order = get_order(order_id)
    if identity["role"] == "CLIENTE" and order["customerId"] != identity["customer_id"]:
        raise ApiError(403, "FORBIDDEN", "Solo puede cancelar sus pedidos")
    if order["status"] not in CANCELLABLE or order.get("inventoryRestored"):
        raise ApiError(409, "INVALID_TRANSITION", "El pedido no se puede cancelar")
    updated = {
        **order,
        "status": "CANCELADO",
        "inventoryRestored": True,
        "updatedAt": utc_now(),
    }
    _, outbox = domain_event("OrderCancelled", updated, identity, correlation)
    transaction = []
    for item in order["items"]:
        transaction.append(
            {
                "Update": {
                    "TableName": PRODUCTS_TABLE,
                    "Key": {"productId": {"S": item["productId"]}},
                    "UpdateExpression": "SET inventory = inventory + :quantity, updatedAt = :updated",
                    "ExpressionAttributeValues": {
                        ":quantity": {"N": str(item["quantity"])},
                        ":updated": {"S": updated["updatedAt"]},
                    },
                }
            }
        )
    transaction.extend(
        [
            {
                "Put": {
                    "TableName": ORDERS_TABLE,
                    "Item": serialize(updated),
                    "ConditionExpression": "#status = :previous AND inventoryRestored = :false",
                    "ExpressionAttributeNames": {"#status": "status"},
                    "ExpressionAttributeValues": {
                        ":previous": {"S": order["status"]},
                        ":false": {"BOOL": False},
                    },
                }
            },
            {
                "Put": {
                    "TableName": AUDIT_TABLE,
                    "Item": serialize(
                        audit(identity, "CANCEL_ORDER", order_id, correlation)
                    ),
                }
            },
            {"Put": {"TableName": OUTBOX_TABLE, "Item": serialize(outbox)}},
            {
                "Put": {
                    "TableName": IDEMPOTENCY_TABLE,
                    "Item": serialize(
                        idempotency_item(scope, key, order_id, "CANCEL_ORDER")
                    ),
                    "ConditionExpression": "attribute_not_exists(idempotencyKey)",
                }
            },
        ]
    )
    client().transact_write_items(
        TransactItems=transaction,
        ClientRequestToken=transaction_token(scope, key),
    )
    return response(200, {"data": updated}, correlation)


HANDLERS = {
    "CREATE": checkout,
    "LIST": list_orders,
    "LIST_MINE": list_mine,
    "GET": get_order_response,
    "UPDATE_STATUS": update_status,
    "CANCEL": cancel_order,
}


def lambda_handler(event, context):
    correlation = correlation_id(event, context)
    action = None
    try:
        action = route_action(event)
        roles = {
            "CREATE": {"CLIENTE"},
            "LIST": {"OPERADOR"},
            "LIST_MINE": {"CLIENTE"},
            "GET": {"OPERADOR", "CLIENTE"},
            "UPDATE_STATUS": {"OPERADOR"},
            "CANCEL": {"OPERADOR", "CLIENTE"},
        }[action]
        identity = require_role(event, roles)
        result = HANDLERS[action](event, identity, correlation)
        log_event(
            "info",
            "order_request_completed",
            correlation,
            action=action,
            actorId=identity["actor_id"],
            role=identity["role"],
        )
        return result
    except ApiError as exc:
        log_event(
            "warning",
            "order_request_rejected",
            correlation,
            action=action,
            statusCode=exc.status_code,
            errorCode=exc.code,
        )
        return error_response(exc, correlation)
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        status = 409 if code in {"TransactionCanceledException", "ConditionalCheckFailedException"} else 500
        return error_response(
            ApiError(
                status,
                "CONCURRENT_MODIFICATION" if status == 409 else "INTERNAL_ERROR",
                "El pedido cambió; recargue e intente nuevamente"
                if status == 409
                else "Error interno del servidor",
            ),
            correlation,
        )
    except Exception:
        log_event("exception", "order_unexpected_error", correlation, action=action)
        return error_response(
            ApiError(500, "INTERNAL_ERROR", "Error interno del servidor"),
            correlation,
        )
