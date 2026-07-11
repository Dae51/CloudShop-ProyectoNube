import json
import logging
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.types import TypeSerializer


AUDIT_TABLE = os.environ.get("AUDIT_TABLE", "OrderEventsAudit")
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
SERIALIZER = TypeSerializer()
dynamodb = boto3.client("dynamodb")


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log_event(level, event_name, **details):
    getattr(LOGGER, level)(json.dumps({"event": event_name, **details}, ensure_ascii=False, default=str))


def serialize_item(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def lambda_handler(event, context):
    detail = event.get("detail") or {}
    order_id = str(detail.get("orderId", "UNKNOWN"))
    event_time = event.get("time") or utc_now()
    audit_item = {
        "eventId": event.get("id") or context.aws_request_id,
        "orderId": order_id,
        "eventTime": event_time,
        "source": event.get("source", "UNKNOWN"),
        "detailType": event.get("detail-type", "UNKNOWN"),
        "receivedAt": utc_now(),
        "eventPayload": json.dumps(event, ensure_ascii=False, default=str),
    }
    dynamodb.put_item(TableName=AUDIT_TABLE, Item=serialize_item(audit_item))
    log_event("info", "order_event_audited", orderId=order_id, eventId=audit_item["eventId"])
    return {"statusCode": 200}
