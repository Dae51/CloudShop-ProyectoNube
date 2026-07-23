import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
OPENAPI = yaml.safe_load((ROOT / "contracts" / "openapi.yaml").read_text())
HTTP_METHODS = {"get", "post", "put", "patch", "delete", "options", "head", "trace"}
OFFICIAL_ROLES = {"ADMINISTRADOR", "OPERADOR", "CLIENTE"}


class OpenApiContractTests(unittest.TestCase):
    def test_contract_has_expected_operations(self):
        operations = [
            operation
            for path_item in OPENAPI["paths"].values()
            for method, operation in path_item.items()
            if method in HTTP_METHODS
        ]

        self.assertEqual(34, len(operations))

    def test_only_official_roles_are_used(self):
        roles = {
            role
            for path_item in OPENAPI["paths"].values()
            for method, operation in path_item.items()
            if method in HTTP_METHODS
            for role in operation.get("x-cloudshop-roles", [])
        }

        self.assertEqual(OFFICIAL_ROLES, roles)
        self.assertNotIn("EJECUTIVO", str(OPENAPI))

    def test_every_operation_has_role_metadata_directly_or_by_ref(self):
        for path, path_item in OPENAPI["paths"].items():
            for method, operation in path_item.items():
                if method not in HTTP_METHODS:
                    continue
                self.assertTrue(
                    "x-cloudshop-roles" in operation or "$ref" in operation,
                    f"{method.upper()} {path} no declara roles",
                )

    def test_registration_is_cognito_and_product_requires_all_fields(self):
        self.assertNotIn("/registro", OPENAPI["paths"])
        required = set(
            OPENAPI["components"]["schemas"]["ProductInput"]["required"]
        )
        self.assertEqual(
            {
                "code",
                "name",
                "description",
                "category",
                "price",
                "inventory",
                "storeId",
            },
            required,
        )


if __name__ == "__main__":
    unittest.main()
