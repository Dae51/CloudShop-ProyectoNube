import json
import logging
import os
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError


ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "Orders")
PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "Products")
STATUS_INDEX = os.environ.get("STATUS_INDEX", "StatusCreatedAtIndex")

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
DESERIALIZER = TypeDeserializer()
dynamodb = boto3.client("dynamodb")

ORDER_STATUSES = ["PENDIENTE", "CONFIRMADO", "EN_PREPARACION", "PAGADO", "ENVIADO", "ENTREGADO", "CANCELADO"]
REVENUE_STATUSES = ["PENDIENTE", "CONFIRMADO", "EN_PREPARACION", "PAGADO", "ENVIADO", "ENTREGADO"]


class ApiError(Exception):
    def __init__(self, status_code, code, message):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def log_event(level, event_name, **details):
    getattr(LOGGER, level)(json.dumps({"event": event_name, **details}, ensure_ascii=False, default=str))


def json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Amz-Date,X-Api-Key,X-Amz-Security-Token,Accept",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body, ensure_ascii=False, default=json_default),
    }


def error_response(status_code, code, message):
    return response(status_code, {"error": {"code": code, "message": message}})


def deserialize_item(item):
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


def query_params(event):
    return event.get("queryStringParameters") or {}


def parse_limit(params, default=10, maximum=100):
    raw_limit = params.get("limit", default)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "INVALID_INPUT", "limit debe ser un entero") from exc
    if limit < 1 or limit > maximum:
        raise ApiError(400, "INVALID_INPUT", f"limit debe estar entre 1 y {maximum}")
    return limit


def parse_iso_bound(params, key):
    value = params.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "INVALID_INPUT", f"{key} no es valido")
    normalized = value.strip()
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ApiError(400, "INVALID_INPUT", f"{key} debe usar formato ISO-8601") from exc
    return normalized


def parse_statuses(params, revenue_only=True):
    raw_statuses = params.get("status") or params.get("statuses")
    allowed = REVENUE_STATUSES if revenue_only else ORDER_STATUSES
    if not raw_statuses:
        return allowed
    statuses = [status.strip().upper() for status in raw_statuses.split(",") if status.strip()]
    if not statuses or any(status not in allowed for status in statuses):
        raise ApiError(400, "INVALID_INPUT", "status contiene valores no validos")
    return statuses


def query_orders_by_status(status, projection, start_at=None, end_at=None):
    names = {
        "#status": "status",
        "#orderId": "orderId",
        "#userId": "userId",
        "#items": "items",
        "#total": "total",
        "#currency": "currency",
        "#createdAt": "createdAt",
    }
    values = {":status": {"S": status}}
    condition = "#status = :status"

    if start_at and end_at:
        condition += " AND createdAt BETWEEN :startAt AND :endAt"
        values[":startAt"] = {"S": start_at}
        values[":endAt"] = {"S": end_at}
    elif start_at:
        condition += " AND createdAt >= :startAt"
        values[":startAt"] = {"S": start_at}
    elif end_at:
        condition += " AND createdAt <= :endAt"
        values[":endAt"] = {"S": end_at}

    request = {
        "TableName": ORDERS_TABLE,
        "IndexName": STATUS_INDEX,
        "KeyConditionExpression": condition,
        "ExpressionAttributeNames": names,
        "ExpressionAttributeValues": values,
        "ProjectionExpression": projection,
    }

    items = []
    while True:
        result = dynamodb.query(**request)
        items.extend(deserialize_item(item) for item in result.get("Items", []))
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return items
        request["ExclusiveStartKey"] = last_key


def query_orders_count_by_status(status, start_at=None, end_at=None):
    names = {"#status": "status"}
    values = {":status": {"S": status}}
    condition = "#status = :status"

    if start_at and end_at:
        condition += " AND createdAt BETWEEN :startAt AND :endAt"
        values[":startAt"] = {"S": start_at}
        values[":endAt"] = {"S": end_at}
    elif start_at:
        condition += " AND createdAt >= :startAt"
        values[":startAt"] = {"S": start_at}
    elif end_at:
        condition += " AND createdAt <= :endAt"
        values[":endAt"] = {"S": end_at}

    request = {
        "TableName": ORDERS_TABLE,
        "IndexName": STATUS_INDEX,
        "KeyConditionExpression": condition,
        "ExpressionAttributeNames": names,
        "ExpressionAttributeValues": values,
        "Select": "COUNT",
    }

    count = 0
    while True:
        result = dynamodb.query(**request)
        count += result.get("Count", 0)
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            return count
        request["ExclusiveStartKey"] = last_key


def iter_report_orders(params, projection):
    start_at = parse_iso_bound(params, "from")
    end_at = parse_iso_bound(params, "to")
    statuses = parse_statuses(params, revenue_only=True)
    for status in statuses:
        for order in query_orders_by_status(status, projection, start_at, end_at):
            yield order


def item_subtotal(item, quantity):
    if item.get("subtotal") is not None:
        return Decimal(str(item["subtotal"]))
    return Decimal(str(item.get("unitPrice") or 0)) * quantity


def total_sales(event):
    params = query_params(event)
    total = Decimal("0")
    order_count = 0
    by_currency = defaultdict(lambda: {"totalSales": Decimal("0"), "orderCount": 0})

    for order in iter_report_orders(params, "#orderId, #total, #currency, #createdAt, #status"):
        amount = Decimal(str(order.get("total", 0)))
        currency = str(order.get("currency", "USD"))
        total += amount
        order_count += 1
        by_currency[currency]["totalSales"] += amount
        by_currency[currency]["orderCount"] += 1

    return response(
        200,
        {
            "data": {
                "totalSales": total,
                "orderCount": order_count,
                "byCurrency": [{"currency": currency, **values} for currency, values in sorted(by_currency.items())],
            }
        },
    )


def sales_by_store(event):
    params = query_params(event)
    limit = parse_limit(params, default=25)
    stores = defaultdict(lambda: {"storeId": None, "totalSales": Decimal("0"), "itemsSold": 0, "orderCount": 0})
    order_ids_by_store = defaultdict(set)

    for order in iter_report_orders(params, "#orderId, #items, #createdAt, #status"):
        order_id = order.get("orderId")
        for item in order.get("items", []):
            store_id = str(item.get("storeId") or "UNKNOWN")
            quantity = int(item.get("quantity", 0))
            subtotal = item_subtotal(item, quantity)
            stores[store_id]["storeId"] = store_id
            stores[store_id]["totalSales"] += subtotal
            stores[store_id]["itemsSold"] += quantity
            order_ids_by_store[store_id].add(order_id)

    data = []
    for store_id, values in stores.items():
        values["orderCount"] = len(order_ids_by_store[store_id])
        data.append(values)
    data.sort(key=lambda item: (item["totalSales"], item["itemsSold"]), reverse=True)
    return response(200, {"data": data[:limit], "count": len(data[:limit])})


def best_selling_products(event):
    params = query_params(event)
    limit = parse_limit(params)
    products = defaultdict(
        lambda: {
            "productId": None,
            "productName": None,
            "storeId": None,
            "quantitySold": 0,
            "totalSales": Decimal("0"),
        }
    )

    for order in iter_report_orders(params, "#items, #createdAt, #status"):
        for item in order.get("items", []):
            product_id = str(item.get("productId", "UNKNOWN"))
            quantity = int(item.get("quantity", 0))
            subtotal = item_subtotal(item, quantity)
            product = products[product_id]
            product["productId"] = product_id
            product["productName"] = item.get("productName") or product["productName"]
            product["storeId"] = item.get("storeId") or product["storeId"]
            product["quantitySold"] += quantity
            product["totalSales"] += subtotal

    data = list(products.values())
    data.sort(key=lambda item: (item["quantitySold"], item["totalSales"]), reverse=True)
    return response(200, {"data": data[:limit], "count": len(data[:limit])})


def out_of_stock_products(event):
    params = query_params(event)
    limit = parse_limit(params, default=50, maximum=200)
    request = {
        "TableName": PRODUCTS_TABLE,
        "ProjectionExpression": "productId, #name, storeId, category, inventory, #status, updatedAt",
        "FilterExpression": "inventory = :zero AND #status = :active",
        "ExpressionAttributeNames": {
            "#name": "name",
            "#status": "status",
        },
        "ExpressionAttributeValues": {
            ":zero": {"N": "0"},
            ":active": {"S": "ACTIVE"},
        },
    }

    products = []
    while True:
        result = dynamodb.scan(**request)
        products.extend(deserialize_item(item) for item in result.get("Items", []))
        if len(products) >= limit:
            products = products[:limit]
            break
        last_key = result.get("LastEvaluatedKey")
        if not last_key:
            break
        request["ExclusiveStartKey"] = last_key

    return response(200, {"data": products, "count": len(products)})


def top_customers(event):
    params = query_params(event)
    limit = parse_limit(params)
    customers = defaultdict(lambda: {"userId": None, "totalPurchases": Decimal("0"), "orderCount": 0})

    for order in iter_report_orders(params, "#orderId, #userId, #total, #createdAt, #status"):
        user_id = str(order.get("userId", "UNKNOWN"))
        customers[user_id]["userId"] = user_id
        customers[user_id]["totalPurchases"] += Decimal(str(order.get("total", 0)))
        customers[user_id]["orderCount"] += 1

    data = list(customers.values())
    data.sort(key=lambda item: (item["totalPurchases"], item["orderCount"]), reverse=True)
    return response(200, {"data": data[:limit], "count": len(data[:limit])})


def orders_by_status(event):
    params = query_params(event)
    start_at = parse_iso_bound(params, "from")
    end_at = parse_iso_bound(params, "to")
    statuses = parse_statuses(params, revenue_only=False)
    data = []
    total_count = 0

    for status in statuses:
        count = query_orders_count_by_status(status, start_at, end_at)
        data.append({"status": status, "orderCount": count})
        total_count += count

    return response(200, {"data": data, "totalOrders": total_count})


def route(event):
    method = (event.get("httpMethod") or "").upper()
    resource = event.get("resource") or ""
    routes = {
        ("GET", "/reportes/ventas/totales"): total_sales,
        ("GET", "/reportes/ventas/tiendas"): sales_by_store,
        ("GET", "/reportes/productos/mas-vendidos"): best_selling_products,
        ("GET", "/reportes/productos/sin-stock"): out_of_stock_products,
        ("GET", "/reportes/clientes/mayores-compras"): top_customers,
        ("GET", "/reportes/pedidos/estados"): orders_by_status,
    }
    handler = routes.get((method, resource))
    if not handler:
        raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")
    return handler(event)


def lambda_handler(event, context):
    try:
        log_event(
            "info",
            "report_request",
            requestId=context.aws_request_id,
            method=event.get("httpMethod"),
            resource=event.get("resource"),
        )
        return route(event)
    except ApiError as exc:
        log_event(
            "warning",
            "report_request_rejected",
            requestId=context.aws_request_id,
            statusCode=exc.status_code,
            errorCode=exc.code,
        )
        return error_response(exc.status_code, exc.code, exc.message)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        log_event("exception", "report_aws_error", requestId=context.aws_request_id, errorCode=error_code)
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    except Exception:
        log_event("exception", "report_unexpected_error", requestId=context.aws_request_id)
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
