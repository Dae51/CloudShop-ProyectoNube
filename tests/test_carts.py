import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Modulos" / "Shared" / "python"))
os.environ.setdefault("CARTS_TABLE", "carts")
os.environ.setdefault("PRODUCTS_TABLE", "products")
MODULE = ROOT / "Modulos" / "Carritos" / "lambda" / "lambda_function.py"
SPEC = importlib.util.spec_from_file_location("carts_lambda", MODULE)
app = importlib.util.module_from_spec(SPEC)
sys.modules["carts_lambda"] = app
SPEC.loader.exec_module(app)
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()


def serialize(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def deserialize(item):
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


class FakeDynamo:
    def __init__(self):
        self.carts = {}
        self.products = {
            "product-1": serialize(
                {"productId": "product-1", "status": "ACTIVE", "inventory": 5}
            )
        }

    def get_item(self, TableName, Key, **kwargs):
        source = self.carts if TableName == "carts" else self.products
        key = Key.get("customerId", Key.get("productId"))["S"]
        return {"Item": source[key]} if key in source else {}

    def put_item(self, Item, **kwargs):
        cart = deserialize(Item)
        self.carts[cart["customerId"]] = Item

    def delete_item(self, Key, **kwargs):
        self.carts.pop(Key["customerId"]["S"], None)


class Context:
    aws_request_id = "request"


class CartLambdaTests(unittest.TestCase):
    def setUp(self):
        self.dynamo = FakeDynamo()
        app._dynamodb = self.dynamo

    @staticmethod
    def event(method, resource, role="CLIENTE", body=None, product_id=None):
        event = {
            "httpMethod": method,
            "resource": resource,
            "requestContext": {
                "authorizer": {"principalId": "sub-1", "role": role},
                "identity": {"cognitoIdentityId": "identity-1"},
            },
            "headers": {},
            "pathParameters": {"productId": product_id} if product_id else {},
        }
        if body is not None:
            event["body"] = json.dumps(body)
        return event

    def test_client_adds_updates_removes_and_clears_item(self):
        added = app.lambda_handler(
            self.event(
                "POST",
                "/carritos/mio/items",
                body={"productId": "product-1", "quantity": 2},
            ),
            Context(),
        )
        self.assertEqual(2, json.loads(added["body"])["data"]["items"][0]["quantity"])

        updated = app.lambda_handler(
            self.event(
                "PATCH",
                "/carritos/mio/items/{productId}",
                body={"quantity": 3},
                product_id="product-1",
            ),
            Context(),
        )
        self.assertEqual(3, json.loads(updated["body"])["data"]["items"][0]["quantity"])

        removed = app.lambda_handler(
            self.event(
                "DELETE",
                "/carritos/mio/items/{productId}",
                product_id="product-1",
            ),
            Context(),
        )
        self.assertEqual([], json.loads(removed["body"])["data"]["items"])

        cleared = app.lambda_handler(
            self.event("DELETE", "/carritos/mio"),
            Context(),
        )
        self.assertEqual(204, cleared["statusCode"])
        self.assertNotIn("body", cleared)

    def test_operator_cannot_use_client_cart(self):
        result = app.lambda_handler(
            self.event("GET", "/carritos/mio", role="OPERADOR"),
            Context(),
        )
        self.assertEqual(403, result["statusCode"])

    def test_stock_is_checked(self):
        result = app.lambda_handler(
            self.event(
                "POST",
                "/carritos/mio/items",
                body={"productId": "product-1", "quantity": 6},
            ),
            Context(),
        )
        self.assertEqual(409, result["statusCode"])

    def test_cart_is_scoped_to_federated_identity(self):
        app.lambda_handler(
            self.event(
                "POST",
                "/carritos/mio/items",
                body={"productId": "product-1", "quantity": 1},
            ),
            Context(),
        )
        stored = deserialize(self.dynamo.carts["identity-1"])
        self.assertEqual("identity-1", stored["customerId"])


if __name__ == "__main__":
    unittest.main()
