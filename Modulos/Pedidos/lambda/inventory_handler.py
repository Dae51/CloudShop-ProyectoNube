import json
import logging
import os
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError


ORDERS_TABLE = os.environ.get("ORDERS_TABLE", "Orders")
PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "Products")
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
dynamodb = boto3.client("dynamodb")


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log_event(level, event_name, **details):
    getattr(LOGGER, level)(json.dumps({"event": event_name, **details}, ensure_ascii=False, default=str))


def build_transaction(detail):
    timestamp = utc_now()
    items = detail.get("items") or []
    transact_items = []

    for item in items:
        product_id = str(item["productId"])
        quantity = int(item["quantity"])
        transact_items.append(
            {
                "Update": {
                    "TableName": PRODUCTS_TABLE,
                    "Key": {"productId": {"S": product_id}},
                    "UpdateExpression": "SET #inventory = #inventory - :qty, updatedAt = :updatedAt",
                    "ConditionExpression": "attribute_exists(productId) AND #status = :active AND #inventory >= :qty",
                    "ExpressionAttributeNames": {"#status": "status", "#inventory": "inventory"},
                    "ExpressionAttributeValues": {
                        ":qty": {"N": str(quantity)},
                        ":active": {"S": "ACTIVE"},
                        ":updatedAt": {"S": timestamp},
                    },
                }
            }
        )

    transact_items.append(
        {
            "Update": {
                "TableName": ORDERS_TABLE,
                "Key": {"orderId": {"S": str(detail["orderId"])}},
                "UpdateExpression": "SET inventoryStatus = :processed, inventoryProcessedAt = :processedAt, updatedAt = :updatedAt",
                "ConditionExpression": "attribute_exists(orderId) AND attribute_not_exists(inventoryProcessedAt)",
                "ExpressionAttributeValues": {
                    ":processed": {"S": "DESCONTADO"},
                    ":processedAt": {"S": timestamp},
                    ":updatedAt": {"S": timestamp},
                },
            }
        }
    )
    return transact_items


def mark_inventory_failed(order_id, reason):
    try:
        timestamp = utc_now()
        dynamodb.update_item(
            TableName=ORDERS_TABLE,
            Key={"orderId": {"S": str(order_id)}},
            UpdateExpression="SET inventoryStatus = :failed, inventoryFailureReason = :reason, updatedAt = :updatedAt",
            ExpressionAttributeValues={":failed": {"S": "FALLIDO"}, ":reason": {"S": reason[:500]}, ":updatedAt": {"S": timestamp}},
        )
    except Exception:
        log_event("exception", "inventory_failure_mark_failed", orderId=order_id)


def lambda_handler(event, context):
    detail = event.get("detail") or {}
    order_id = detail.get("orderId", "UNKNOWN")
    try:
        log_event("info", "inventory_event_received", requestId=context.aws_request_id, orderId=order_id)
        transact_items = build_transaction(detail)
        dynamodb.transact_write_items(TransactItems=transact_items)
        log_event("info", "inventory_discounted", orderId=order_id, items=len(detail.get("items") or []))
        return {"statusCode": 200}
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "AWS_ERROR")
        if error_code in {"TransactionCanceledException", "ConditionalCheckFailedException"}:
            mark_inventory_failed(order_id, "Inventario insuficiente, producto inexistente o evento duplicado")
            log_event("warning", "inventory_conflict", orderId=order_id, errorCode=error_code)
            return {"statusCode": 409}
        mark_inventory_failed(order_id, error_code)
        log_event("exception", "inventory_aws_error", orderId=order_id, errorCode=error_code)
        raise
    except Exception:
        mark_inventory_failed(order_id, "Error inesperado")
        log_event("exception", "inventory_unexpected_error", orderId=order_id)
        raise
