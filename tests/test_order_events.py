import importlib.util
import os
import sys
import unittest
from pathlib import Path

from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError


ROOT = Path(__file__).resolve().parents[1]
LAMBDA_DIR = ROOT / "Modulos" / "Pedidos" / "lambda"
SERIALIZER = TypeSerializer()


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, LAMBDA_DIR / filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


os.environ.setdefault("EVENT_BUS_NAME", "bus")
os.environ.setdefault("OUTBOX_TABLE", "outbox")
relay = load("outbox_relay", "outbox_relay.py")

os.environ.setdefault("USERS_TABLE", "users")
os.environ.setdefault("IDEMPOTENCY_TABLE", "idempotency")
os.environ.setdefault("SES_SENDER", "sender@example.com")
os.environ.setdefault("SES_CONFIGURATION_SET", "config")
os.environ.setdefault("SES_OVERRIDE_RECIPIENT", "demo@example.com")
notification = load("notification", "notification.py")


def serialize(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


class Context:
    aws_request_id = "request"


class FakeEvents:
    def __init__(self):
        self.entries = []

    def put_events(self, Entries):
        self.entries.extend(Entries)
        return {"FailedEntryCount": 0}


class FakeRelayDynamo:
    def __init__(self, already_published=False):
        self.updated = 0
        self.already_published = already_published

    def update_item(self, **kwargs):
        if self.already_published:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException"}},
                "UpdateItem",
            )
        self.updated += 1


class FakeNotificationDynamo:
    def __init__(self):
        self.idempotency = {}
        self.updates = []

    def get_item(self, TableName, Key, **kwargs):
        if TableName == "users":
            return {"Item": {"email": {"S": "user@example.com"}}}
        value = self.idempotency.get(Key["idempotencyKey"]["S"])
        return {"Item": value} if value else {}

    def put_item(self, Item, **kwargs):
        self.idempotency[Item["idempotencyKey"]["S"]] = Item

    def update_item(self, Key, ExpressionAttributeValues, **kwargs):
        key = Key["idempotencyKey"]["S"]
        self.idempotency[key].update(
            {
                "status": ExpressionAttributeValues[":sent"],
                "messageId": ExpressionAttributeValues[":message"],
            }
        )
        self.updates.append(key)


class FakeSes:
    def __init__(self):
        self.requests = []

    def send_email(self, **kwargs):
        self.requests.append(kwargs)
        return {"MessageId": "ses-message-1"}


class OrderEventTests(unittest.TestCase):
    @staticmethod
    def payload():
        return {
            "version": 1,
            "eventId": "event-1",
            "eventType": "OrderCreated",
            "occurredAt": "2026-07-24T00:00:00Z",
            "correlationId": "correlation-1",
            "actorId": "sub-1",
            "orderId": "order-1",
            "customerId": "identity-1",
            "status": "PENDIENTE",
            "total": "21.00",
        }

    def stream_event(self):
        return {
            "Records": [
                {
                    "eventName": "INSERT",
                    "dynamodb": {
                        "SequenceNumber": "1",
                        "NewImage": serialize(
                            {
                                "eventId": "event-1",
                                "status": "PENDING",
                                "payload": self.payload(),
                            }
                        ),
                    },
                }
            ]
        }

    def test_outbox_relay_publishes_and_marks_event(self):
        events = FakeEvents()
        dynamo = FakeRelayDynamo()
        relay._events = events
        relay._dynamodb = dynamo

        result = relay.lambda_handler(self.stream_event(), Context())

        self.assertEqual([], result["batchItemFailures"])
        self.assertEqual(1, len(events.entries))
        self.assertEqual("OrderCreated", events.entries[0]["DetailType"])
        self.assertEqual(1, dynamo.updated)

    def test_outbox_relay_tolerates_already_published_retry(self):
        events = FakeEvents()
        relay._events = events
        relay._dynamodb = FakeRelayDynamo(already_published=True)

        result = relay.lambda_handler(self.stream_event(), Context())

        self.assertEqual([], result["batchItemFailures"])

    def test_notification_is_idempotent_and_records_message_id(self):
        dynamo = FakeNotificationDynamo()
        ses = FakeSes()
        notification._dynamodb = dynamo
        notification._ses = ses
        event = {"detail": self.payload()}

        first = notification.lambda_handler(event, Context())
        second = notification.lambda_handler(event, Context())

        self.assertEqual("sent", first["status"])
        self.assertEqual("duplicate", second["status"])
        self.assertEqual(1, len(ses.requests))
        self.assertEqual(
            ["demo@example.com"],
            ses.requests[0]["Destination"]["ToAddresses"],
        )
        self.assertEqual("ses-message-1", first["messageId"])

    def test_unconfigured_ses_is_not_reported_as_sent(self):
        original = notification.SES_SENDER
        notification.SES_SENDER = ""
        notification._dynamodb = FakeNotificationDynamo()
        notification._ses = FakeSes()
        try:
            result = notification.lambda_handler(
                {"detail": self.payload()},
                Context(),
            )
        finally:
            notification.SES_SENDER = original

        self.assertEqual("skipped_unconfigured", result["status"])


if __name__ == "__main__":
    unittest.main()
