import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

from boto3.dynamodb.types import TypeDeserializer


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Modulos" / "Shared" / "python"))
os.environ.setdefault("STORES_TABLE", "stores")
os.environ.setdefault("AUDIT_TABLE", "audit")
MODULE = ROOT / "Modulos" / "Tiendas" / "lambda" / "lambda_function.py"
SPEC = importlib.util.spec_from_file_location("stores_lambda", MODULE)
app = importlib.util.module_from_spec(SPEC)
sys.modules["stores_lambda"] = app
SPEC.loader.exec_module(app)
DESERIALIZER = TypeDeserializer()


def deserialize(item):
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


class FakeDynamo:
    def __init__(self):
        self.stores = {}
        self.audits = []

    def get_item(self, Key, **kwargs):
        item = self.stores.get(Key["storeId"]["S"])
        return {"Item": item} if item else {}

    def scan(self, **kwargs):
        values = list(self.stores.values())
        if "FilterExpression" in kwargs:
            values = [item for item in values if deserialize(item)["status"] == "ACTIVE"]
        return {"Items": values}

    def transact_write_items(self, TransactItems):
        for operation in TransactItems:
            put = operation["Put"]
            item = deserialize(put["Item"])
            if put["TableName"] == "stores":
                self.stores[item["storeId"]] = put["Item"]
            else:
                self.audits.append(item)


class Context:
    aws_request_id = "request"


class StoreLambdaTests(unittest.TestCase):
    def setUp(self):
        self.dynamo = FakeDynamo()
        app._dynamodb = self.dynamo

    @staticmethod
    def event(method, resource, role, body=None, store_id=None):
        event = {
            "httpMethod": method,
            "resource": resource,
            "requestContext": {
                "authorizer": {"principalId": f"user-{role}", "role": role}
            },
            "headers": {},
            "pathParameters": {"storeId": store_id} if store_id else {},
        }
        if body is not None:
            event["body"] = json.dumps(body)
        return event

    def create(self):
        result = app.lambda_handler(
            self.event(
                "POST",
                "/tiendas",
                "ADMINISTRADOR",
                {"name": "Central", "description": "Tienda principal"},
            ),
            Context(),
        )
        return json.loads(result["body"])["data"]

    def test_admin_creates_and_audits_store(self):
        store = self.create()

        self.assertEqual("ACTIVE", store["status"])
        self.assertEqual("CREATE_STORE", self.dynamo.audits[-1]["action"])
        self.assertIn("correlationId", self.dynamo.audits[-1])

    def test_operator_cannot_create_store(self):
        result = app.lambda_handler(
            self.event(
                "POST",
                "/tiendas",
                "OPERADOR",
                {"name": "No", "description": "No"},
            ),
            Context(),
        )

        self.assertEqual(403, result["statusCode"])

    def test_client_can_list_active_stores(self):
        self.create()
        result = app.lambda_handler(
            self.event("GET", "/tiendas", "CLIENTE"),
            Context(),
        )

        self.assertEqual(200, result["statusCode"])
        self.assertEqual(1, len(json.loads(result["body"])["data"]))

    def test_admin_deactivates_store(self):
        store = self.create()
        result = app.lambda_handler(
            self.event(
                "DELETE",
                "/tiendas/{storeId}",
                "ADMINISTRADOR",
                store_id=store["storeId"],
            ),
            Context(),
        )

        self.assertEqual("INACTIVE", json.loads(result["body"])["data"]["status"])


if __name__ == "__main__":
    unittest.main()
