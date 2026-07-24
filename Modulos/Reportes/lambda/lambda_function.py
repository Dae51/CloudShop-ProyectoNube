import os
from collections import defaultdict
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer

from cloudshop_common import (
    ApiError,
    correlation_id,
    error_response,
    log_event,
    require_role,
    response,
)


ORDERS_TABLE = os.environ["ORDERS_TABLE"]
PRODUCTS_TABLE = os.environ["PRODUCTS_TABLE"]
DESERIALIZER = TypeDeserializer()
ORDER_STATES = (
    "PENDIENTE",
    "CONFIRMADO",
    "EN_PREPARACION",
    "ENVIADO",
    "ENTREGADO",
    "CANCELADO",
)
_dynamodb = None


def client():
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.client("dynamodb")
    return _dynamodb


def deserialize(item):
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


def scan_all(table_name):
    items = []
    request = {"TableName": table_name}
    while True:
        result = client().scan(**request)
        items.extend(deserialize(item) for item in result.get("Items", []))
        if "LastEvaluatedKey" not in result:
            return items
        request["ExclusiveStartKey"] = result["LastEvaluatedKey"]


def route_action(event):
    key = ((event.get("httpMethod") or "").upper(), event.get("resource") or "")
    action = {
        ("GET", "/reportes/ventas/total"): "TOTAL_SALES",
        ("GET", "/reportes/ventas/por-tienda"): "SALES_BY_STORE",
        ("GET", "/reportes/productos/mas-vendidos"): "TOP_PRODUCTS",
        ("GET", "/reportes/productos/agotados"): "OUT_OF_STOCK",
        ("GET", "/reportes/clientes/mas-compras"): "TOP_CUSTOMERS",
        ("GET", "/reportes/pedidos/por-estado"): "ORDERS_BY_STATUS",
    }.get(key)
    if not action:
        raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")
    return action


def delivered_orders():
    return [
        order
        for order in scan_all(ORDERS_TABLE)
        if order.get("status") == "ENTREGADO"
    ]


def total_sales():
    orders = delivered_orders()
    return {
        "currency": "USD",
        "totalSales": sum((Decimal(str(order.get("total", 0))) for order in orders), Decimal("0")),
        "deliveredOrders": len(orders),
    }


def sales_by_store():
    totals = defaultdict(lambda: {"totalSales": Decimal("0"), "units": 0})
    for order in delivered_orders():
        for item in order.get("items", []):
            record = totals[item["storeId"]]
            record["totalSales"] += Decimal(str(item.get("subtotal", 0)))
            record["units"] += int(item.get("quantity", 0))
    return [
        {"storeId": store_id, **values}
        for store_id, values in sorted(
            totals.items(), key=lambda entry: (-entry[1]["totalSales"], entry[0])
        )
    ]


def top_products():
    totals = defaultdict(
        lambda: {"name": "", "units": 0, "totalSales": Decimal("0")}
    )
    for order in delivered_orders():
        for item in order.get("items", []):
            record = totals[item["productId"]]
            record["name"] = item.get("name", "")
            record["units"] += int(item.get("quantity", 0))
            record["totalSales"] += Decimal(str(item.get("subtotal", 0)))
    return [
        {"productId": product_id, **values}
        for product_id, values in sorted(
            totals.items(), key=lambda entry: (-entry[1]["units"], entry[0])
        )[:10]
    ]


def out_of_stock():
    return sorted(
        [
            {
                "productId": product["productId"],
                "code": product["code"],
                "name": product["name"],
                "storeId": product["storeId"],
            }
            for product in scan_all(PRODUCTS_TABLE)
            if product.get("status") == "ACTIVE"
            and int(product.get("inventory", 0)) == 0
        ],
        key=lambda product: product["code"],
    )


def top_customers():
    totals = defaultdict(lambda: {"orders": 0, "totalSpent": Decimal("0")})
    for order in delivered_orders():
        record = totals[order["customerId"]]
        record["orders"] += 1
        record["totalSpent"] += Decimal(str(order.get("total", 0)))
    # customerId is the federated Identity Pool identity. It is intentionally
    # not joined by email or other PII because that relationship is not
    # guaranteed by the current user schema.
    return [
        {"customerId": customer_id, **values}
        for customer_id, values in sorted(
            totals.items(), key=lambda entry: (-entry[1]["orders"], -entry[1]["totalSpent"])
        )[:10]
    ]


def orders_by_status():
    counts = {status: 0 for status in ORDER_STATES}
    for order in scan_all(ORDERS_TABLE):
        status = order.get("status")
        if status in counts:
            counts[status] += 1
    return [{"status": status, "orders": counts[status]} for status in ORDER_STATES]


HANDLERS = {
    "TOTAL_SALES": total_sales,
    "SALES_BY_STORE": sales_by_store,
    "TOP_PRODUCTS": top_products,
    "OUT_OF_STOCK": out_of_stock,
    "TOP_CUSTOMERS": top_customers,
    "ORDERS_BY_STATUS": orders_by_status,
}


def lambda_handler(event, context):
    correlation = correlation_id(event, context)
    action = None
    try:
        action = route_action(event)
        identity = require_role(event, {"ADMINISTRADOR"})
        result = response(200, {"data": HANDLERS[action]()}, correlation)
        log_event(
            "info",
            "report_request_completed",
            correlation,
            action=action,
            actorId=identity["actor_id"],
        )
        return result
    except ApiError as exc:
        log_event(
            "warning",
            "report_request_rejected",
            correlation,
            action=action,
            statusCode=exc.status_code,
            errorCode=exc.code,
        )
        return error_response(exc, correlation)
    except Exception:
        log_event(
            "exception",
            "report_unexpected_error",
            correlation,
            action=action,
            statusCode=500,
            errorCode="INTERNAL_ERROR",
        )
        return error_response(
            ApiError(500, "INTERNAL_ERROR", "Error interno del servidor"),
            correlation,
        )
