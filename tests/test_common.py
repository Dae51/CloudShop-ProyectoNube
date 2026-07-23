import json
import sys
import unittest
from pathlib import Path


sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "Modulos" / "Shared" / "python"),
)

import cloudshop_common as common  # noqa: E402


class Context:
    aws_request_id = "not-a-uuid"


class CommonRuntimeTests(unittest.TestCase):
    def test_identity_uses_cognito_role_and_subject(self):
        event = {
            "requestContext": {
                "identity": {
                    "userArn": (
                        "arn:aws:sts::123456789012:"
                        "assumed-role/cloudshop-dev-cliente/CognitoIdentityCredentials"
                    ),
                    "cognitoIdentityId": "us-east-1:identity",
                    "cognitoAuthenticationProvider": (
                        "cognito-idp.us-east-1.amazonaws.com/us-east-1_pool,"
                        "cognito-idp.us-east-1.amazonaws.com/us-east-1_pool:"
                        "CognitoSignIn:user-sub"
                    ),
                }
            }
        }

        identity = common.identity_from_event(event)

        self.assertEqual("CLIENTE", identity["role"])
        self.assertEqual("user-sub", identity["actor_id"])
        self.assertEqual("us-east-1:identity", identity["customer_id"])

    def test_privileged_role_does_not_match_arbitrary_suffix(self):
        event = {
            "requestContext": {
                "identity": {
                    "userArn": "arn:aws:iam::123456789012:user/administrador-falso",
                    "caller": "caller",
                }
            }
        }

        identity = common.identity_from_event(event)

        self.assertIsNone(identity["role"])

    def test_require_role_returns_403(self):
        event = {
            "requestContext": {
                "authorizer": {"principalId": "user-1", "role": "CLIENTE"}
            }
        }

        with self.assertRaises(common.ApiError) as raised:
            common.require_role(event, {"ADMINISTRADOR"})

        self.assertEqual(403, raised.exception.status_code)

    def test_error_response_has_correlation_id_and_cors(self):
        result = common.error_response(
            common.ApiError(403, "FORBIDDEN", "No"),
            "7cb33a1e-05ad-48c9-b9f6-946718bd8900",
        )

        body = json.loads(result["body"])
        self.assertEqual(403, result["statusCode"])
        self.assertEqual(
            result["headers"]["X-Correlation-Id"],
            body["error"]["correlationId"],
        )
        self.assertEqual("*", result["headers"]["Access-Control-Allow-Origin"])

    def test_invalid_idempotency_key_rejected(self):
        with self.assertRaises(common.ApiError) as raised:
            common.idempotency_key({"headers": {"Idempotency-Key": "not-a-uuid"}})

        self.assertEqual("INVALID_INPUT", raised.exception.code)


if __name__ == "__main__":
    unittest.main()
