import json
import logging
import os
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError


EVENT_BUS_NAME = os.environ["EVENT_BUS_NAME"]
OUTBOX_TABLE = os.environ["OUTBOX_TABLE"]
DESERIALIZER = TypeDeserializer()
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
_events = None
_dynamodb = None


def clients():
    global _events, _dynamodb
    if _events is None:
        _events = boto3.client("events")
    if _dynamodb is None:
        _dynamodb = boto3.client("dynamodb")
    return _events, _dynamodb


def deserialize(image):
    return {key: DESERIALIZER.deserialize(value) for key, value in image.items()}


def lambda_handler(event, context):
    failures = []
    events, dynamodb = clients()
    for record in event.get("Records", []):
        sequence = record.get("dynamodb", {}).get("SequenceNumber", "unknown")
        try:
            if record.get("eventName") not in {"INSERT", "MODIFY"}:
                continue
            image = record.get("dynamodb", {}).get("NewImage") or {}
            outbox = deserialize(image)
            if outbox.get("status") != "PENDING":
                continue
            payload = outbox["payload"]
            result = events.put_events(
                Entries=[
                    {
                        "EventBusName": EVENT_BUS_NAME,
                        "Source": "cloudshop.orders",
                        "DetailType": payload["eventType"],
                        "Detail": json.dumps(payload, default=str),
                    }
                ]
            )
            if result.get("FailedEntryCount"):
                raise RuntimeError("EventBridge rechazó el evento")
            try:
                dynamodb.update_item(
                    TableName=OUTBOX_TABLE,
                    Key={"eventId": {"S": outbox["eventId"]}},
                    UpdateExpression="SET #status = :published, publishedAt = :published_at",
                    ConditionExpression="#status = :pending",
                    ExpressionAttributeNames={"#status": "status"},
                    ExpressionAttributeValues={
                        ":published": {"S": "PUBLISHED"},
                        ":pending": {"S": "PENDING"},
                        ":published_at": {
                            "S": datetime.now(timezone.utc)
                            .isoformat()
                            .replace("+00:00", "Z")
                        },
                    },
                )
            except ClientError as exc:
                if (
                    exc.response.get("Error", {}).get("Code")
                    != "ConditionalCheckFailedException"
                ):
                    raise
        except Exception as exc:
            LOGGER.exception(
                json.dumps(
                    {
                        "event": "outbox_relay_failed",
                        "sequenceNumber": sequence,
                        "correlationId": locals()
                        .get("outbox", {})
                        .get("payload", {})
                        .get("correlationId", "UNKNOWN"),
                        "statusCode": 500,
                        "errorCode": type(exc).__name__,
                    }
                )
            )
            failures.append({"itemIdentifier": sequence})
    return {"batchItemFailures": failures}
