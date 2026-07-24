import importlib.util
import json
import os
import sys
import unittest
from decimal import Decimal
from pathlib import Path

from boto3.dynamodb.types import TypeSerializer


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Modulos" / "Shared" / "python"))
for key, value in {
    "ORDERS_TABLE": "orders",
    "PRODUCTS_TABLE": "products",
    "USERS_TABLE": "users",
}.items():
    os.environ.setdefault(key, value)
MODULE = ROOT / "Modulos" / "Reportes" / "lambda" / "lambda_function.py"
SPEC = importlib.util.spec_from_file_location("reports_lambda", MODULE)
app = importlib.util.module_from_spec(SPEC)
sys.modules["reports_lambda"] = app
SPEC.loader.exec_module(app)
SERIALIZER = TypeSerializer()


def serialize(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


class FakeDynamo:
    def __init__(self):
        self.tables = {
            "orders": [
                {
                    "orderId": "o1",
                    "customerId": "customer-1",
                    "status": "ENTREGADO",
                    "total": Decimal("25.00"),
                    "items": [
                        {
                            "productId": "p1",
                            "storeId": "s1",
                            "name": "Café",
                            "quantity": 2,
                            "subtotal": Decimal("20.00"),
                        },
                        {
                            "productId": "p2",
                            "storeId": "s2",
                            "name": "Pan",
                            "quantity": 1,
                            "subtotal": Decimal("5.00"),
                        },
                    ],
                },
                {
                    "orderId": "o2",
                    "customerId": "customer-1",
                    "status": "CANCELADO",
                    "total": Decimal("100"),
                    "items": [],
                },
                {
                    "orderId": "o3",
                    "customerId": "customer-2",
                    "status": "PENDIENTE",
                    "total": Decimal("9"),
                    "items": [],
                },
            ],
            "products": [
                {
                    "productId": "p1",
                    "code": "CAF-1",
                    "name": "Café",
                    "storeId": "s1",
                    "status": "ACTIVE",
                    "inventory": 0,
                },
                {
                    "productId": "p2",
                    "code": "PAN-1",
                    "name": "Pan",
                    "storeId": "s2",
                    "status": "ACTIVE",
                    "inventory": 4,
                },
            ],
            "users": [],
        }

    def scan(self, TableName, **kwargs):
        return {"Items": [serialize(item) for item in self.tables[TableName]]}


def event(resource, role="administrador"):
    return {
        "httpMethod": "GET",
        "resource": resource,
        "headers": {"X-Correlation-Id": "f51f60de-1811-4ec8-95fa-0df55b3702de"},
        "requestContext": {
            "identity": {
                "userArn": f"arn:aws:sts::123456789012:assumed-role/cloudshop-dev-{role}/session",
                "caller": "caller",
            }
        },
    }


class ReportsLambdaTests(unittest.TestCase):
    def setUp(self):
        app._dynamodb = FakeDynamo()

    def call(self, resource, role="administrador"):
        result = app.lambda_handler(event(resource, role), None)
        return result["statusCode"], json.loads(result["body"])

    def test_dashboard_calculates_all_six_metrics(self):
        status, total = self.call("/reportes/ventas/total")
        self.assertEqual(200, status)
        self.assertEqual(25, total["data"]["totalSales"])
        self.assertEqual(1, total["data"]["deliveredOrders"])

        _, stores = self.call("/reportes/ventas/por-tienda")
        self.assertEqual("s1", stores["data"][0]["storeId"])
        self.assertEqual(20, stores["data"][0]["totalSales"])

        _, products = self.call("/reportes/productos/mas-vendidos")
        self.assertEqual(2, products["data"][0]["units"])

        _, stock = self.call("/reportes/productos/agotados")
        self.assertEqual(["p1"], [item["productId"] for item in stock["data"]])

        _, customers = self.call("/reportes/clientes/mas-compras")
        self.assertEqual("customer-1", customers["data"][0]["customerId"])

        _, states = self.call("/reportes/pedidos/por-estado")
        counts = {item["status"]: item["orders"] for item in states["data"]}
        self.assertEqual(1, counts["ENTREGADO"])
        self.assertEqual(1, counts["CANCELADO"])
        self.assertEqual(1, counts["PENDIENTE"])

    def test_reports_reject_non_administrator_with_403(self):
        status, body = self.call("/reportes/ventas/total", "operador")
        self.assertEqual(403, status)
        self.assertEqual("FORBIDDEN", body["error"]["code"])
