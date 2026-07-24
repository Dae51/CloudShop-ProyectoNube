import json
import sys
import unittest
from pathlib import Path


LAMBDA_DIR = Path(__file__).resolve().parents[1] / "lambda"
sys.path.insert(0, str(LAMBDA_DIR))

import lambda_function as app  # noqa: E402


class FakeDynamoDBClient:
    def __init__(self):
        self.products = {}
        self.audits = []
        self.stores = {
            "store-1": app.serialize_item(
                {"storeId": "store-1", "name": "Principal", "status": "ACTIVE"}
            ),
            "store-inactive": app.serialize_item(
                {
                    "storeId": "store-inactive",
                    "name": "Cerrada",
                    "status": "INACTIVE",
                }
            ),
        }

    def seed_product(self, product):
        self.products[product["productId"]] = app.serialize_item(product)

    def get_item(self, TableName, Key, **kwargs):
        if TableName == app.STORES_TABLE:
            store_id = Key["storeId"]["S"]
            item = self.stores.get(store_id)
            return {"Item": item} if item else {}
        product_id = Key["productId"]["S"]
        item = self.products.get(product_id)
        return {"Item": item} if item else {}

    def scan(self, TableName, **kwargs):
        items = list(self.products.values())
        if "FilterExpression" in kwargs:
            items = [item for item in items if app.deserialize_item(item)["status"] == "ACTIVE"]
        return {"Items": items}

    def query(self, TableName, ExpressionAttributeValues, **kwargs):
        store_id = ExpressionAttributeValues[":store_id"]["S"]
        items = [
            item
            for item in self.products.values()
            if app.deserialize_item(item)["storeId"] == store_id
            and app.deserialize_item(item)["status"] == "ACTIVE"
        ]
        return {"Items": items}

    def put_item(self, TableName, Item, **kwargs):
        if TableName == app.AUDIT_TABLE:
            self.audits.append(app.deserialize_item(Item))
        return {}

    def transact_write_items(self, TransactItems):
        for operation in TransactItems:
            put = operation["Put"]
            item = app.deserialize_item(put["Item"])
            if put["TableName"] == app.PRODUCTS_TABLE:
                self.products[item["productId"]] = put["Item"]
            elif put["TableName"] == app.AUDIT_TABLE:
                self.audits.append(item)
        return {}


class Context:
    aws_request_id = "test-request"


class ProductLambdaTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeDynamoDBClient()
        app._dynamodb_client = self.client
        self.product = {
            "productId": "product-1",
            "code": "SKU-001",
            "name": "Laptop",
            "description": "Laptop empresarial",
            "category": "Tecnología",
            "price": app.Decimal("999.99"),
            "inventory": 10,
            "storeId": "store-1",
            "status": "ACTIVE",
            "createdAt": "2026-07-04T10:00:00Z",
            "updatedAt": "2026-07-04T10:00:00Z",
        }
        self.client.seed_product(self.product)

    def event(self, method, resource, role, body=None, path_parameters=None):
        event = {
            "httpMethod": method,
            "resource": resource,
            "requestContext": {
                "authorizer": {"principalId": f"user-{role.lower()}", "role": role}
            },
            "pathParameters": path_parameters or {},
        }
        if body is not None:
            event["body"] = json.dumps(body)
        return event

    @staticmethod
    def body(result):
        return json.loads(result["body"])

    def product_payload(self):
        return {
            "code": "SKU-002",
            "name": "Monitor",
            "description": "Monitor 27 pulgadas",
            "category": "Tecnología",
            "price": 249.99,
            "inventory": 8,
            "storeId": "store-1",
        }

    def test_admin_can_create_product(self):
        event = self.event("POST", "/productos", "Administrador", self.product_payload())

        result = app.lambda_handler(event, Context())

        self.assertEqual(201, result["statusCode"])
        created = self.body(result)["data"]
        self.assertEqual("ACTIVE", created["status"])
        self.assertIn(created["productId"], self.client.products)

    def test_cliente_cannot_create_product(self):
        event = self.event("POST", "/productos", "Cliente", self.product_payload())

        result = app.lambda_handler(event, Context())

        self.assertEqual(403, result["statusCode"])
        self.assertEqual("FORBIDDEN", self.body(result)["error"]["code"])

    def test_product_requires_active_owning_store(self):
        payload = self.product_payload()
        payload["storeId"] = "store-inactive"
        event = self.event("POST", "/productos", "Administrador", payload)

        result = app.lambda_handler(event, Context())

        self.assertEqual(409, result["statusCode"])
        self.assertEqual("INACTIVE_STORE", self.body(result)["error"]["code"])

    def test_product_rejects_fields_outside_openapi_contract(self):
        payload = self.product_payload()
        payload["unexpected"] = True
        result = app.lambda_handler(
            self.event("POST", "/productos", "Administrador", payload),
            Context(),
        )
        self.assertEqual(400, result["statusCode"])
        self.assertEqual("INVALID_INPUT", self.body(result)["error"]["code"])

    def test_product_rejects_limits_and_excess_price_precision(self):
        for field, value in (
            ("code", "x" * 65),
            ("name", "x" * 161),
            ("description", "x" * 2001),
            ("category", "x" * 101),
            ("inventory", 1_000_001),
            ("price", 10.001),
        ):
            with self.subTest(field=field):
                payload = self.product_payload()
                payload[field] = value
                result = app.lambda_handler(
                    self.event("POST", "/productos", "Administrador", payload),
                    Context(),
                )
                self.assertEqual(400, result["statusCode"])

    def test_product_rejects_numeric_strings_and_multiple_roles(self):
        for field, value in (("price", "10.50"), ("inventory", "8")):
            with self.subTest(field=field):
                payload = self.product_payload()
                payload[field] = value
                result = app.lambda_handler(
                    self.event("POST", "/productos", "Administrador", payload),
                    Context(),
                )
                self.assertEqual(400, result["statusCode"])
        self.assertIsNone(app.normalize_role(["ADMINISTRADOR", "CLIENTE"]))

    def test_cliente_can_list_products(self):
        event = self.event("GET", "/productos", "Cliente")

        result = app.lambda_handler(event, Context())

        self.assertEqual(200, result["statusCode"])
        self.assertEqual(1, self.body(result)["count"])

    def test_operador_can_update_inventory(self):
        event = self.event(
            "PATCH",
            "/productos/{productId}/inventario",
            "Operador",
            {"inventory": 7},
            {"productId": "product-1"},
        )

        result = app.lambda_handler(event, Context())

        self.assertEqual(200, result["statusCode"])
        self.assertEqual(7, self.body(result)["data"]["inventory"])

    def test_operador_cannot_delete_product(self):
        event = self.event(
            "DELETE",
            "/productos/{productId}",
            "Operador",
            path_parameters={"productId": "product-1"},
        )

        result = app.lambda_handler(event, Context())

        self.assertEqual(403, result["statusCode"])
        self.assertEqual("ACTIVE", app.deserialize_item(self.client.products["product-1"])["status"])

    def test_admin_soft_deletes_product(self):
        event = self.event(
            "DELETE",
            "/productos/{productId}",
            "Administrador",
            path_parameters={"productId": "product-1"},
        )

        result = app.lambda_handler(event, Context())

        self.assertEqual(200, result["statusCode"])
        self.assertEqual("DELETED", self.body(result)["data"]["status"])

    def test_product_deletion_creates_audit_record(self):
        event = self.event(
            "DELETE",
            "/productos/{productId}",
            "Administrador",
            path_parameters={"productId": "product-1"},
        )

        app.lambda_handler(event, Context())

        audit = self.client.audits[-1]
        self.assertEqual("DELETE_PRODUCT", audit["accion"])
        self.assertEqual("product-1", audit["resourceId"])
        self.assertEqual("EXITOSO", audit["resultado"])

    def test_inventory_update_creates_audit_record(self):
        event = self.event(
            "PATCH",
            "/productos/{productId}/inventario",
            "Operador",
            {"inventory": 4},
            {"productId": "product-1"},
        )

        app.lambda_handler(event, Context())

        audit = self.client.audits[-1]
        self.assertEqual("UPDATE_PRODUCT_INVENTORY", audit["accion"])
        self.assertEqual("product-1", audit["resourceId"])
        self.assertEqual("EXITOSO", audit["resultado"])


if __name__ == "__main__":
    unittest.main()
