import importlib.util
import os
import sys
import unittest
from pathlib import Path

from botocore.exceptions import ClientError


os.environ.setdefault("USERS_TABLE", "users")
os.environ.setdefault("AUDIT_TABLE", "audit")
MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "Modulos"
    / "Autenticacion"
    / "lambda"
    / "post_confirmation.py"
)
SPEC = importlib.util.spec_from_file_location("post_confirmation", MODULE_PATH)
app = importlib.util.module_from_spec(SPEC)
sys.modules["post_confirmation"] = app
SPEC.loader.exec_module(app)


class FakeDynamo:
    def __init__(self):
        self.transactions = []
        self.exists = False

    def transact_write_items(self, TransactItems):
        if self.exists:
            raise ClientError(
                {"Error": {"Code": "TransactionCanceledException"}},
                "TransactWriteItems",
            )
        self.exists = True
        self.transactions.append(TransactItems)

    def get_item(self, **kwargs):
        return {"Item": {"userId": {"S": "sub-1"}}} if self.exists else {}


class FakeCognito:
    def __init__(self):
        self.calls = []

    def admin_add_user_to_group(self, **kwargs):
        self.calls.append(kwargs)


class Context:
    aws_request_id = "correlation-1"


class PostConfirmationTests(unittest.TestCase):
    def setUp(self):
        self.dynamo = FakeDynamo()
        self.cognito = FakeCognito()
        app._dynamodb = self.dynamo
        app._cognito = self.cognito
        self.event = {
            "userPoolId": "pool",
            "userName": "student@example.com",
            "request": {
                "userAttributes": {
                    "sub": "sub-1",
                    "name": "Student",
                    "email": "Student@Example.com",
                }
            },
        }

    def test_new_user_is_always_cliente(self):
        app.lambda_handler(self.event, Context())

        transaction = self.dynamo.transactions[0]
        user_item = transaction[0]["Put"]["Item"]
        self.assertEqual("CLIENTE", user_item["role"]["S"])
        self.assertEqual("student@example.com", user_item["email"]["S"])
        self.assertEqual("CLIENTE", self.cognito.calls[0]["GroupName"])

    def test_retry_is_idempotent(self):
        app.lambda_handler(self.event, Context())
        result = app.lambda_handler(self.event, Context())

        self.assertIs(self.event, result)
        self.assertEqual(1, len(self.dynamo.transactions))
        self.assertEqual(2, len(self.cognito.calls))


if __name__ == "__main__":
    unittest.main()
