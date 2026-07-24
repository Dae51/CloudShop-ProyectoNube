import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Modulos" / "Shared" / "python"))
for key, value in {
    "ORDERS_TABLE": "orders",
    "CARTS_TABLE": "carts",
    "PRODUCTS_TABLE": "products",
    "STORES_TABLE": "stores",
    "AUDIT_TABLE": "audit",
    "OUTBOX_TABLE": "outbox",
    "IDEMPOTENCY_TABLE": "idempotency",
}.items():
    os.environ.setdefault(key, value)
MODULE = ROOT / "Modulos" / "Pedidos" / "lambda" / "lambda_function.py"
SPEC = importlib.util.spec_from_file_location("orders_lambda", MODULE)
app = importlib.util.module_from_spec(SPEC)
sys.modules["orders_lambda"] = app
SPEC.loader.exec_module(app)
SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()


def serialize(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def deserialize(item):
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


class FakeDynamo:
    def __init__(self):
        self.tables = {
            "orders": {},
            "carts": {
                "identity-1": serialize(
                    {
                        "customerId": "identity-1",
                        "items": [{"productId": "product-1", "quantity": 2}],
                        "version": 1,
                        "updatedAt": "2026-07-24T00:00:00Z",
                    }
                )
            },
            "products": {
                "product-1": serialize(
                    {
                        "productId": "product-1",
                        "storeId": "store-1",
                        "name": "Laptop",
                        "price": app.Decimal("10.50"),
                        "inventory": 5,
                        "status": "ACTIVE",
                        "updatedAt": "2026-07-24T00:00:00Z",
                    }
                )
            },
            "stores": {
                "store-1": serialize(
                    {
                        "storeId": "store-1",
                        "name": "Principal",
                        "status": "ACTIVE",
                    }
                )
            },
            "audit": {},
            "outbox": {},
            "idempotency": {},
        }
        self.tokens = []

    def get_item(self, TableName, Key, **kwargs):
        key_value = next(iter(Key.values()))["S"]
        item = self.tables[TableName].get(key_value)
        return {"Item": item} if item else {}

    def scan(self, TableName, **kwargs):
        return {"Items": list(self.tables[TableName].values())}

    def query(self, TableName, ExpressionAttributeValues, **kwargs):
        customer = ExpressionAttributeValues[":customer"]["S"]
        items = [
            item
            for item in self.tables[TableName].values()
            if deserialize(item)["customerId"] == customer
        ]
        return {"Items": items}

    def transact_write_items(self, TransactItems, **kwargs):
        self.tokens.append(kwargs.get("ClientRequestToken"))
        for operation in TransactItems:
            if "ConditionCheck" in operation:
                continue
            if "Update" in operation:
                update = operation["Update"]
                product_id = update["Key"]["productId"]["S"]
                product = deserialize(self.tables["products"][product_id])
                quantity = int(
                    update["ExpressionAttributeValues"][":quantity"]["N"]
                )
                if "inventory - :quantity" in update["UpdateExpression"]:
                    product["inventory"] -= quantity
                else:
                    product["inventory"] += quantity
                self.tables["products"][product_id] = serialize(product)
                continue
            if "Delete" in operation:
                delete = operation["Delete"]
                customer_id = delete["Key"]["customerId"]["S"]
                self.tables[delete["TableName"]].pop(customer_id, None)
                continue
            put = operation["Put"]
            item = deserialize(put["Item"])
            key_name = {
                "orders": "orderId",
                "audit": "auditId",
                "outbox": "eventId",
                "idempotency": "idempotencyKey",
            }[put["TableName"]]
            self.tables[put["TableName"]][item[key_name]] = put["Item"]


class Context:
    aws_request_id = "request"


class OrderLambdaTests(unittest.TestCase):
    CHECKOUT_KEY = "11111111-1111-4111-8111-111111111111"
    CANCEL_KEY = "22222222-2222-4222-8222-222222222222"

    def setUp(self):
        self.dynamo = FakeDynamo()
        app._dynamodb = self.dynamo

    @staticmethod
    def event(
        method,
        resource,
        role="CLIENTE",
        identity="identity-1",
        body=None,
        order_id=None,
        key=None,
    ):
        event = {
            "httpMethod": method,
            "resource": resource,
            "requestContext": {
                "authorizer": {"principalId": "sub-1", "role": role},
                "identity": {"cognitoIdentityId": identity},
            },
            "headers": {"Idempotency-Key": key} if key else {},
            "pathParameters": {"orderId": order_id} if order_id else {},
        }
        if body is not None:
            event["body"] = json.dumps(body)
        return event

    def checkout(self):
        return app.lambda_handler(
            self.event(
                "POST",
                "/pedidos",
                key=self.CHECKOUT_KEY,
            ),
            Context(),
        )

    def test_checkout_is_atomic_shape_and_idempotent(self):
        created = self.checkout()
        order = json.loads(created["body"])["data"]

        self.assertEqual(201, created["statusCode"])
        self.assertEqual("PENDIENTE", order["status"])
        self.assertEqual(21, order["total"])
        self.assertEqual(
            3,
            deserialize(self.dynamo.tables["products"]["product-1"])["inventory"],
        )
        self.assertNotIn("identity-1", self.dynamo.tables["carts"])
        self.assertEqual(1, len(self.dynamo.tables["audit"]))
        self.assertEqual(1, len(self.dynamo.tables["outbox"]))
        self.assertEqual(1, len(self.dynamo.tables["idempotency"]))

        replayed = self.checkout()
        self.assertEqual(200, replayed["statusCode"])
        self.assertEqual("true", replayed["headers"]["Idempotent-Replayed"])
        self.assertEqual(
            3,
            deserialize(self.dynamo.tables["products"]["product-1"])["inventory"],
        )

    def test_checkout_rejects_insufficient_stock(self):
        product = deserialize(self.dynamo.tables["products"]["product-1"])
        product["inventory"] = 1
        self.dynamo.tables["products"]["product-1"] = serialize(product)

        result = self.checkout()

        self.assertEqual(409, result["statusCode"])
        self.assertEqual(
            "INSUFFICIENT_STOCK",
            json.loads(result["body"])["error"]["code"],
        )
        self.assertEqual({}, self.dynamo.tables["orders"])

    def test_checkout_rejects_inactive_store_without_side_effects(self):
        store = deserialize(self.dynamo.tables["stores"]["store-1"])
        store["status"] = "INACTIVE"
        self.dynamo.tables["stores"]["store-1"] = serialize(store)

        result = self.checkout()

        self.assertEqual(409, result["statusCode"])
        self.assertEqual("INACTIVE_STORE", json.loads(result["body"])["error"]["code"])
        self.assertEqual(
            5,
            deserialize(self.dynamo.tables["products"]["product-1"])["inventory"],
        )
        self.assertIn("identity-1", self.dynamo.tables["carts"])
        self.assertEqual({}, self.dynamo.tables["orders"])

    def test_state_machine_rejects_skips_and_terminal_transitions(self):
        self.assertTrue(app.transition_allowed("PENDIENTE", "CONFIRMADO"))
        self.assertTrue(app.transition_allowed("ENVIADO", "ENTREGADO"))
        self.assertFalse(app.transition_allowed("PENDIENTE", "ENVIADO"))
        self.assertFalse(app.transition_allowed("ENTREGADO", "CANCELADO"))
        self.assertFalse(app.transition_allowed("CANCELADO", "CONFIRMADO"))

    def test_client_cannot_update_status(self):
        order = json.loads(self.checkout()["body"])["data"]
        result = app.lambda_handler(
            self.event(
                "PATCH",
                "/pedidos/{orderId}/estado",
                body={"status": "CONFIRMADO"},
                order_id=order["orderId"],
                key=self.CANCEL_KEY,
            ),
            Context(),
        )
        self.assertEqual(403, result["statusCode"])

    def test_cancel_restores_inventory_exactly_once(self):
        order = json.loads(self.checkout()["body"])["data"]
        cancelled = app.lambda_handler(
            self.event(
                "POST",
                "/pedidos/{orderId}/cancelacion",
                order_id=order["orderId"],
                key=self.CANCEL_KEY,
            ),
            Context(),
        )
        self.assertEqual(
            "CANCELADO",
            json.loads(cancelled["body"])["data"]["status"],
        )
        self.assertEqual(
            5,
            deserialize(self.dynamo.tables["products"]["product-1"])["inventory"],
        )
        replayed = app.lambda_handler(
            self.event(
                "POST",
                "/pedidos/{orderId}/cancelacion",
                order_id=order["orderId"],
                key=self.CANCEL_KEY,
            ),
            Context(),
        )
        self.assertEqual(200, replayed["statusCode"])
        self.assertEqual(
            5,
            deserialize(self.dynamo.tables["products"]["product-1"])["inventory"],
        )

    def test_cancel_replay_does_not_leak_order_to_another_client(self):
        order = json.loads(self.checkout()["body"])["data"]
        owner_result = app.lambda_handler(
            self.event(
                "POST",
                "/pedidos/{orderId}/cancelacion",
                order_id=order["orderId"],
                key=self.CANCEL_KEY,
            ),
            Context(),
        )
        attacker_result = app.lambda_handler(
            self.event(
                "POST",
                "/pedidos/{orderId}/cancelacion",
                identity="identity-2",
                order_id=order["orderId"],
                key=self.CANCEL_KEY,
            ),
            Context(),
        )

        self.assertEqual(200, owner_result["statusCode"])
        self.assertEqual(403, attacker_result["statusCode"])

    def test_transaction_conflict_replays_winner_without_client_token(self):
        original = self.dynamo.transact_write_items

        def concurrent_winner(TransactItems, **kwargs):
            self.assertNotIn("ClientRequestToken", kwargs)
            original(TransactItems)
            raise app.ClientError(
                {"Error": {"Code": "TransactionCanceledException"}},
                "TransactWriteItems",
            )

        self.dynamo.transact_write_items = concurrent_winner
        result = self.checkout()

        self.assertEqual(200, result["statusCode"])
        self.assertEqual("true", result["headers"]["Idempotent-Replayed"])
        self.assertEqual(
            3,
            deserialize(self.dynamo.tables["products"]["product-1"])["inventory"],
        )
        self.assertEqual(1, len(self.dynamo.tables["orders"]))

    def test_client_cannot_read_another_customers_order(self):
        order = json.loads(self.checkout()["body"])["data"]
        result = app.lambda_handler(
            self.event(
                "GET",
                "/pedidos/{orderId}",
                identity="identity-2",
                order_id=order["orderId"],
            ),
            Context(),
        )
        self.assertEqual(403, result["statusCode"])

    def test_transaction_tokens_are_scoped_by_operation(self):
        token_a = app.transaction_token("CHECKOUT#identity-1", self.CHECKOUT_KEY)
        token_b = app.transaction_token("CANCEL#order-1", self.CHECKOUT_KEY)
        self.assertNotEqual(token_a, token_b)
        self.assertEqual(36, len(token_a))


if __name__ == "__main__":
    unittest.main()
