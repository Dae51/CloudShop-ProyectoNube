import json
import logging
import os
import time

import boto3
from boto3.dynamodb.types import TypeDeserializer
from botocore.exceptions import ClientError


USERS_TABLE = os.environ["USERS_TABLE"]
IDEMPOTENCY_TABLE = os.environ["IDEMPOTENCY_TABLE"]
SES_SENDER = os.environ.get("SES_SENDER", "")
SES_CONFIGURATION_SET = os.environ.get("SES_CONFIGURATION_SET", "")
SES_OVERRIDE_RECIPIENT = os.environ.get("SES_OVERRIDE_RECIPIENT", "")
DESERIALIZER = TypeDeserializer()
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
_dynamodb = None
_ses = None


def clients():
    global _dynamodb, _ses
    if _dynamodb is None:
        _dynamodb = boto3.client("dynamodb")
    if _ses is None:
        _ses = boto3.client("sesv2")
    return _dynamodb, _ses


def claim_event(dynamodb, key, detail):
    now = int(time.time())
    try:
        dynamodb.update_item(
            TableName=IDEMPOTENCY_TABLE,
            Key={"idempotencyKey": {"S": key}},
            UpdateExpression=(
                "SET #status = :processing, leaseUntil = :lease, "
                "createdAt = if_not_exists(createdAt, :created), "
                "expiresAt = :expires"
            ),
            ConditionExpression=(
                "attribute_not_exists(idempotencyKey) "
                "OR #status IN (:pending, :failed) "
                "OR (#status = :processing AND leaseUntil < :now)"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":processing": {"S": "PROCESSING"},
                ":pending": {"S": "PENDING"},
                ":failed": {"S": "FAILED"},
                ":now": {"N": str(now)},
                ":lease": {"N": str(now + 60)},
                ":created": {"S": detail["occurredAt"]},
                ":expires": {"N": str(now + 30 * 24 * 3600)},
            },
        )
        return True
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") != "ConditionalCheckFailedException":
            raise
        existing = dynamodb.get_item(
            TableName=IDEMPOTENCY_TABLE,
            Key={"idempotencyKey": {"S": key}},
            ConsistentRead=True,
        ).get("Item")
        if existing and existing.get("status", {}).get("S") == "SENT":
            return False
        raise RuntimeError("Notificación ya está siendo procesada") from exc


def mark_failed(dynamodb, key):
    dynamodb.update_item(
        TableName=IDEMPOTENCY_TABLE,
        Key={"idempotencyKey": {"S": key}},
        UpdateExpression="SET #status = :failed REMOVE leaseUntil",
        ConditionExpression="#status = :processing",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":failed": {"S": "FAILED"},
            ":processing": {"S": "PROCESSING"},
        },
    )


def lambda_handler(event, context):
    detail = event["detail"]
    event_id = detail["eventId"]
    key = f"MAIL#{event_id}"
    correlation = detail["correlationId"]
    dynamodb, ses = clients()

    if not SES_SENDER:
        LOGGER.warning(
            json.dumps(
                {
                    "event": "email_skipped_unconfigured",
                    "eventId": event_id,
                    "correlationId": correlation,
                }
            )
        )
        return {"status": "skipped_unconfigured", "eventId": event_id}

    if not claim_event(dynamodb, key, detail):
        return {"status": "duplicate", "eventId": event_id}

    user = dynamodb.get_item(
        TableName=USERS_TABLE,
        Key={"userId": {"S": detail["actorId"]}},
        ConsistentRead=True,
    ).get("Item")
    if not user:
        mark_failed(dynamodb, key)
        raise RuntimeError("Usuario del pedido no encontrado")
    recipient = SES_OVERRIDE_RECIPIENT or DESERIALIZER.deserialize(user["email"])

    subject = (
        f"CloudShop: pedido {detail['orderId']} "
        f"{'creado' if detail['eventType'] == 'OrderCreated' else 'actualizado'}"
    )
    request = {
        "FromEmailAddress": SES_SENDER,
        "Destination": {"ToAddresses": [recipient]},
        "Content": {
            "Simple": {
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {
                    "Text": {
                        "Data": (
                            f"Pedido: {detail['orderId']}\n"
                            f"Estado: {detail['status']}\n"
                            f"Correlation ID: {correlation}\n"
                        ),
                        "Charset": "UTF-8",
                    }
                },
            }
        },
    }
    if SES_CONFIGURATION_SET:
        request["ConfigurationSetName"] = SES_CONFIGURATION_SET
    try:
        sent = ses.send_email(**request)
    except Exception:
        mark_failed(dynamodb, key)
        raise
    dynamodb.update_item(
        TableName=IDEMPOTENCY_TABLE,
        Key={"idempotencyKey": {"S": key}},
        UpdateExpression="SET #status = :sent, messageId = :message REMOVE leaseUntil",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":sent": {"S": "SENT"},
            ":message": {"S": sent["MessageId"]},
        },
    )
    LOGGER.info(
        json.dumps(
            {
                "event": "email_sent",
                "eventId": event_id,
                "orderId": detail["orderId"],
                "correlationId": correlation,
                "messageId": sent["MessageId"],
            }
        )
    )
    return {"status": "sent", "eventId": event_id, "messageId": sent["MessageId"]}
