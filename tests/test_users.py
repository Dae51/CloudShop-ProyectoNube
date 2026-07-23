import importlib.util
import json
import os
import sys
import unittest
from pathlib import Path

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Modulos" / "Shared" / "python"))
os.environ.setdefault("USERS_TABLE", "users")
os.environ.setdefault("AUDIT_TABLE", "audit")
os.environ.setdefault("USER_POOL_ID", "pool")
MODULE_PATH = ROOT / "Modulos" / "Usuarios" / "lambda" / "lambda_function.py"
SPEC = importlib.util.spec_from_file_location("users_lambda", MODULE_PATH)
app = importlib.util.module_from_spec(SPEC)
sys.modules["users_lambda"] = app
SPEC.loader.exec_module(app)

SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()


def serialize(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def deserialize(item):
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


class FakeDynamo:
    def __init__(self):
        self.users = {
            "client-1": serialize(
                {
                    "userId": "client-1",
                    "username": "client",
                    "name": "Client",
                    "email": "client@example.com",
                    "role": "CLIENTE",
                    "status": "ACTIVE",
                    "createdAt": "2026-07-23T00:00:00Z",
                    "updatedAt": "2026-07-23T00:00:00Z",
                }
            ),
            "operator-1": serialize(
                {
                    "userId": "operator-1",
                    "username": "operator",
                    "name": "Operator",
                    "email": "operator@example.com",
                    "role": "OPERADOR",
                    "status": "ACTIVE",
                    "createdAt": "2026-07-23T00:00:00Z",
                    "updatedAt": "2026-07-23T00:00:00Z",
                }
            ),
        }
        self.audits = []

    def get_item(self, TableName, Key, **kwargs):
        item = self.users.get(Key["userId"]["S"])
        return {"Item": item} if item else {}

    def scan(self, **kwargs):
        return {"Items": list(self.users.values())}

    def transact_write_items(self, TransactItems):
        for operation in TransactItems:
            if "Put" in operation:
                self.audits.append(deserialize(operation["Put"]["Item"]))
                continue
            update = operation["Update"]
            user_id = update["Key"]["userId"]["S"]
            user = deserialize(self.users[user_id])
            values = update["ExpressionAttributeValues"]
            if ":name" in values:
                user["name"] = values[":name"]["S"]
            if ":role" in values:
                user["role"] = values[":role"]["S"]
            if ":inactive" in values:
                user["status"] = values[":inactive"]["S"]
            user["updatedAt"] = values[":updated"]["S"]
            self.users[user_id] = serialize(user)


class FakeCognito:
    def __init__(self):
        self.groups = {"operator": ["OPERADOR"], "client": ["CLIENTE"]}

    def admin_list_groups_for_user(self, Username, **kwargs):
        return {"Groups": [{"GroupName": value} for value in self.groups[Username]]}

    def admin_remove_user_from_group(self, Username, GroupName, **kwargs):
        if GroupName in self.groups[Username]:
            self.groups[Username].remove(GroupName)

    def admin_add_user_to_group(self, Username, GroupName, **kwargs):
        if GroupName not in self.groups[Username]:
            self.groups[Username].append(GroupName)

    def admin_disable_user(self, **kwargs):
        return {}

    def admin_enable_user(self, **kwargs):
        return {}


class Context:
    aws_request_id = "request"


class UsersLambdaTests(unittest.TestCase):
    def setUp(self):
        self.dynamo = FakeDynamo()
        self.cognito = FakeCognito()
        app._dynamodb = self.dynamo
        app._cognito = self.cognito

    @staticmethod
    def event(method, resource, role, actor, user_id=None, body=None):
        event = {
            "httpMethod": method,
            "resource": resource,
            "requestContext": {
                "authorizer": {"principalId": actor, "role": role}
            },
            "pathParameters": {"userId": user_id} if user_id else {},
            "headers": {},
        }
        if body is not None:
            event["body"] = json.dumps(body)
        return event

    def test_cliente_cannot_read_another_profile(self):
        result = app.lambda_handler(
            self.event(
                "GET",
                "/usuarios/{userId}",
                "CLIENTE",
                "client-1",
                "operator-1",
            ),
            Context(),
        )

        self.assertEqual(403, result["statusCode"])

    def test_cliente_can_update_own_name_but_not_role(self):
        result = app.lambda_handler(
            self.event(
                "PUT",
                "/usuarios/{userId}",
                "CLIENTE",
                "client-1",
                "client-1",
                {"name": "New Name"},
            ),
            Context(),
        )

        self.assertEqual(200, result["statusCode"])
        self.assertEqual("New Name", deserialize(self.dynamo.users["client-1"])["name"])
        self.assertEqual("CLIENTE", deserialize(self.dynamo.users["client-1"])["role"])

    def test_cliente_cannot_list_users(self):
        result = app.lambda_handler(
            self.event("GET", "/usuarios", "CLIENTE", "client-1"),
            Context(),
        )

        self.assertEqual(403, result["statusCode"])

    def test_admin_changes_role_and_audits(self):
        result = app.lambda_handler(
            self.event(
                "PATCH",
                "/usuarios/{userId}/rol",
                "ADMINISTRADOR",
                "admin-1",
                "operator-1",
                {"role": "ADMINISTRADOR"},
            ),
            Context(),
        )

        self.assertEqual(200, result["statusCode"])
        self.assertEqual(["ADMINISTRADOR"], self.cognito.groups["operator"])
        self.assertEqual(
            "ADMINISTRADOR",
            deserialize(self.dynamo.users["operator-1"])["role"],
        )
        self.assertEqual("CHANGE_USER_ROLE", self.dynamo.audits[-1]["action"])

    def test_non_official_role_rejected(self):
        result = app.lambda_handler(
            self.event(
                "PATCH",
                "/usuarios/{userId}/rol",
                "ADMINISTRADOR",
                "admin-1",
                "operator-1",
                {"role": "EJECUTIVO"},
            ),
            Context(),
        )

        self.assertEqual(400, result["statusCode"])


if __name__ == "__main__":
    unittest.main()
