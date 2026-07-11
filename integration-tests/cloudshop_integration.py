#!/usr/bin/env python3
"""
CloudShop Enterprise integration evidence runner.

The script is intentionally stdlib-only for API calls. It signs API Gateway
requests with AWS SigV4 and uses the AWS CLI for verification against
DynamoDB, CloudWatch Logs, CloudWatch Metrics, EventBridge evidence, and
Terraform deployment checks.
"""

from __future__ import annotations

import argparse
import configparser
import datetime as dt
import hashlib
import hmac
import json
import os
import pathlib
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


ROOT = pathlib.Path(__file__).resolve().parents[1]
EVIDENCE_DIR = pathlib.Path(__file__).resolve().parent / "evidence"


class IntegrationError(Exception):
    pass


@dataclass
class AwsCredentials:
    access_key: str
    secret_key: str
    session_token: str | None = None


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def save_evidence(name: str, payload: Any) -> pathlib.Path:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / f"{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')}-{name}.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    return path


def run(command: list[str], cwd: pathlib.Path | None = None, env: dict[str, str] | None = None, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(command, cwd=str(cwd) if cwd else None, env=env, text=True, capture_output=True)
    if check and result.returncode != 0:
        raise IntegrationError(
            f"Command failed: {' '.join(command)}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def aws_cli(args: list[str], profile: str | None, region: str | None, check: bool = True) -> Any:
    command = ["aws", *args]
    if profile:
        command.extend(["--profile", profile])
    if region:
        command.extend(["--region", region])
    command.extend(["--output", "json"])
    result = run(command, check=check)
    if not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"raw": result.stdout}


def load_config(path: pathlib.Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("terraformDirectory", str(ROOT))
    terraform_directory = pathlib.Path(data["terraformDirectory"])
    if not terraform_directory.is_absolute():
        data["terraformDirectory"] = str((path.parent / terraform_directory).resolve())
    data.setdefault("stageName", "dev")
    data.setdefault("region", "us-east-2")
    data.setdefault("evidence", {})
    data.setdefault("apiNames", {})
    data.setdefault("apiUrls", {})
    data.setdefault("tables", {})
    data.setdefault("lambdas", {})
    return data


def terraform_outputs(terraform_dir: pathlib.Path) -> dict[str, str]:
    result = run(["terraform", "output", "-json"], cwd=terraform_dir, check=False)
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    payload = json.loads(result.stdout)
    return {key: value.get("value") for key, value in payload.items()}


def merge_outputs(config: dict[str, Any]) -> dict[str, Any]:
    outputs = terraform_outputs(pathlib.Path(config["terraformDirectory"]))
    output_map = {
        "usuarios_api_url": ("apiUrls", "usuarios"),
        "productos_api_url": ("apiUrls", "productos"),
        "tiendas_api_url": ("apiUrls", "tiendas"),
        "compras_api_url": ("apiUrls", "compras"),
        "pedidos_api_url": ("apiUrls", "pedidos"),
        "reportes_api_url": ("apiUrls", "reportes"),
        "observabilidad_dashboard_name": ("observability", "dashboardName"),
    }
    config.setdefault("observability", {})
    for output_name, (section, key) in output_map.items():
        if outputs.get(output_name):
            config.setdefault(section, {})[key] = outputs[output_name]
    return config


def credentials_from_env(prefix: str) -> AwsCredentials | None:
    access_key = os.getenv(f"{prefix}_AWS_ACCESS_KEY_ID")
    secret_key = os.getenv(f"{prefix}_AWS_SECRET_ACCESS_KEY")
    token = os.getenv(f"{prefix}_AWS_SESSION_TOKEN")
    if access_key and secret_key:
        return AwsCredentials(access_key, secret_key, token)
    return None


def credentials_from_profile(profile: str | None) -> AwsCredentials:
    if not profile:
        access_key = os.getenv("AWS_ACCESS_KEY_ID")
        secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        token = os.getenv("AWS_SESSION_TOKEN")
        if access_key and secret_key:
            return AwsCredentials(access_key, secret_key, token)
        raise IntegrationError("No AWS credentials found in environment.")

    exported = run(["aws", "configure", "export-credentials", "--profile", profile, "--format", "json"], check=False)
    if exported.returncode == 0 and exported.stdout.strip():
        payload = json.loads(exported.stdout)
        return AwsCredentials(payload["AccessKeyId"], payload["SecretAccessKey"], payload.get("SessionToken"))

    credentials_file = pathlib.Path(os.getenv("AWS_SHARED_CREDENTIALS_FILE", pathlib.Path.home() / ".aws" / "credentials"))
    parser = configparser.ConfigParser()
    parser.read(credentials_file)
    if not parser.has_section(profile):
        raise IntegrationError(f"AWS profile '{profile}' was not found and export-credentials failed.")
    section = parser[profile]
    return AwsCredentials(
        section["aws_access_key_id"],
        section["aws_secret_access_key"],
        section.get("aws_session_token"),
    )


def get_credentials(config: dict[str, Any], kind: str) -> tuple[AwsCredentials, str | None]:
    profile = config.get("profiles", {}).get(kind)
    env_prefix = f"CLOUDSHOP_{kind.upper()}"
    credentials = credentials_from_env(env_prefix) or credentials_from_profile(profile)
    return credentials, profile


def sign_key(secret_key: str, date_stamp: str, region: str, service: str) -> bytes:
    key_date = hmac.new(("AWS4" + secret_key).encode(), date_stamp.encode(), hashlib.sha256).digest()
    key_region = hmac.new(key_date, region.encode(), hashlib.sha256).digest()
    key_service = hmac.new(key_region, service.encode(), hashlib.sha256).digest()
    return hmac.new(key_service, b"aws4_request", hashlib.sha256).digest()


def signed_request(
    method: str,
    url: str,
    region: str,
    credentials: AwsCredentials,
    body: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    parsed = urllib.parse.urlparse(url)
    payload = b"" if body is None else json.dumps(body, separators=(",", ":"), default=str).encode("utf-8")
    timestamp = dt.datetime.now(dt.timezone.utc)
    amz_date = timestamp.strftime("%Y%m%dT%H%M%SZ")
    date_stamp = timestamp.strftime("%Y%m%d")

    canonical_uri = parsed.path or "/"
    canonical_query = parsed.query
    request_headers = {
        "host": parsed.netloc,
        "x-amz-date": amz_date,
        "content-type": "application/json",
        **(headers or {}),
    }
    if credentials.session_token:
        request_headers["x-amz-security-token"] = credentials.session_token

    signed_headers = ";".join(sorted(key.lower() for key in request_headers))
    canonical_headers = "".join(f"{key.lower()}:{str(request_headers[key]).strip()}\n" for key in sorted(request_headers))
    payload_hash = hashlib.sha256(payload).hexdigest()
    canonical_request = "\n".join([method, canonical_uri, canonical_query, canonical_headers, signed_headers, payload_hash])
    credential_scope = f"{date_stamp}/{region}/execute-api/aws4_request"
    string_to_sign = "\n".join(
        ["AWS4-HMAC-SHA256", amz_date, credential_scope, hashlib.sha256(canonical_request.encode()).hexdigest()]
    )
    signature = hmac.new(sign_key(credentials.secret_key, date_stamp, region, "execute-api"), string_to_sign.encode(), hashlib.sha256).hexdigest()
    authorization = (
        f"AWS4-HMAC-SHA256 Credential={credentials.access_key}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    request_headers["Authorization"] = authorization

    request = urllib.request.Request(url, data=payload if method != "GET" else None, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return {"status": response.status, "headers": dict(response.headers), "body": json.loads(raw) if raw else None}
    except urllib.error.HTTPError as error:
        raw = error.read().decode("utf-8")
        try:
            parsed_body = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed_body = raw
        return {"status": error.code, "headers": dict(error.headers), "body": parsed_body}


def api_url(config: dict[str, Any], api: str, path: str) -> str:
    base = config["apiUrls"].get(api)
    if not base:
        raise IntegrationError(f"Missing apiUrls.{api} in configuration or terraform outputs.")
    return f"{base.rstrip('/')}{path}"


def discover_rest_api_id(config: dict[str, Any], profile: str | None, api_key: str) -> str:
    api_name = config.get("apiNames", {}).get(api_key)
    if not api_name:
        raise IntegrationError(f"Missing apiNames.{api_key} in configuration.")
    apis = aws_cli(["apigateway", "get-rest-apis"], profile, config["region"])
    matches = [item for item in apis.get("items", []) if item.get("name") == api_name]
    if not matches:
        raise IntegrationError(f"Could not find API Gateway named {api_name}.")
    return matches[0]["id"]


def filter_logs(config: dict[str, Any], profile: str | None, log_group: str, pattern: str | None = None, minutes: int = 15) -> list[dict[str, Any]]:
    start = int((time.time() - minutes * 60) * 1000)
    args = ["logs", "filter-log-events", "--log-group-name", log_group, "--start-time", str(start), "--limit", "25"]
    if pattern:
        args.extend(["--filter-pattern", pattern])
    result = aws_cli(args, profile, config["region"], check=False)
    return result.get("events", []) if isinstance(result, dict) else []


def wait_for(description: str, timeout_seconds: int, interval_seconds: int, callback):
    deadline = time.time() + timeout_seconds
    last_value = None
    while time.time() < deadline:
        last_value = callback()
        if last_value:
            return last_value
        time.sleep(interval_seconds)
    raise IntegrationError(f"Timed out waiting for {description}. Last value: {last_value}")


def dynamodb_get(config: dict[str, Any], profile: str | None, table: str, key: dict[str, Any]) -> dict[str, Any]:
    result = aws_cli(["dynamodb", "get-item", "--table-name", table, "--key", json.dumps(key)], profile, config["region"])
    return result.get("Item", {})


def case_unauthorized_access(config: dict[str, Any]) -> dict[str, Any]:
    unauthorized_credentials, unauthorized_profile = get_credentials(config, "unauthorized")
    admin_credentials, admin_profile = get_credentials(config, "admin")
    product_body = dict(config["testData"]["product"])
    product_body["code"] = f"UNAUTH-{int(time.time())}"

    response = signed_request(
        "POST",
        api_url(config, "productos", "/productos"),
        config["region"],
        unauthorized_credentials,
        product_body,
    )
    if response["status"] != 403:
        raise IntegrationError(f"Expected HTTP 403 for unauthorized access, got {response['status']}: {response['body']}")

    rest_api_id = discover_rest_api_id(config, admin_profile, "productos")
    log_group = f"API-Gateway-Execution-Logs_{rest_api_id}/{config['stageName']}"
    logs = wait_for(
        "API Gateway failed authorization logs",
        90,
        10,
        lambda: filter_logs(config, admin_profile, log_group, minutes=20),
    )
    evidence = {
        "case": "Unauthorized Access",
        "timestamp": utc_now(),
        "request": {"method": "POST", "path": "/productos", "profile": unauthorized_profile},
        "response": response,
        "apiGatewayLogGroup": log_group,
        "failedAuthorizationLogs": logs,
        "passed": response["status"] == 403 and bool(logs),
    }
    save_evidence("case1-unauthorized-access", evidence)
    return evidence


def case_complete_order_flow(config: dict[str, Any]) -> dict[str, Any]:
    admin_credentials, admin_profile = get_credentials(config, "admin")
    product = dict(config["testData"]["product"])
    product["code"] = f"FLOW-{int(time.time())}"
    product["inventory"] = int(product.get("inventory", 5))

    create_product = signed_request("POST", api_url(config, "productos", "/productos"), config["region"], admin_credentials, product)
    if create_product["status"] != 201:
        raise IntegrationError(f"Product creation failed: {create_product}")
    product_data = create_product["body"]["data"]
    product_id = product_data["productId"]

    order_body = dict(config["testData"]["order"])
    order_body["items"] = [
        {
            "productId": product_id,
            "productName": product_data["name"],
            "storeId": product_data.get("storeId", product["storeId"]),
            "quantity": 1,
            "unitPrice": str(product_data["price"]),
        }
    ]
    create_order = signed_request("POST", api_url(config, "pedidos", "/pedidos"), config["region"], admin_credentials, order_body)
    if create_order["status"] != 201:
        raise IntegrationError(f"Order creation failed: {create_order}")
    order = create_order["body"]["data"]
    order_id = order["orderId"]

    tables = config["tables"]
    order_item = wait_for(
        "order stored in DynamoDB",
        60,
        5,
        lambda: dynamodb_get(config, admin_profile, tables["orders"], {"orderId": {"S": order_id}}),
    )

    inventory_item = wait_for(
        "inventory updated by EventBridge consumer",
        90,
        5,
        lambda: (
            dynamodb_get(config, admin_profile, tables["products"], {"productId": {"S": product_id}})
            if int(dynamodb_get(config, admin_profile, tables["products"], {"productId": {"S": product_id}}).get("inventory", {}).get("N", product["inventory"])) < product["inventory"]
            else None
        ),
    )

    audit_result = wait_for(
        "audit record created",
        90,
        5,
        lambda: aws_cli(
            [
                "dynamodb",
                "query",
                "--table-name",
                tables["orderEventsAudit"],
                "--index-name",
                "OrderIdEventTimeIndex",
                "--key-condition-expression",
                "orderId = :orderId",
                "--expression-attribute-values",
                json.dumps({":orderId": {"S": order_id}}),
            ],
            admin_profile,
            config["region"],
            check=False,
        ).get("Items", []),
    )

    lambda_logs = {}
    for logical, group in config["logGroups"].items():
        if logical in {"orders", "inventory", "audit", "email"}:
            lambda_logs[logical] = filter_logs(config, admin_profile, group, f'"{order_id}"', minutes=30)

    email_success_logs = [event for event in lambda_logs.get("email", []) if "order_email_sent" in event.get("message", "")]
    email_error_logs = [event for event in lambda_logs.get("email", []) if "order_email_failed" in event.get("message", "")]
    evidence = {
        "case": "Complete Order Flow",
        "timestamp": utc_now(),
        "productCreationResponse": create_product,
        "orderCreationResponse": create_order,
        "orderDynamoDbItem": order_item,
        "inventoryDynamoDbItem": inventory_item,
        "eventBridgeEvidence": {
            "orderEventPublicationStatus": order_item.get("eventPublicationStatus"),
            "auditRecordCount": len(audit_result),
        },
        "auditRecords": audit_result,
        "sesNotificationEvidence": {
            "emailSentLogFound": bool(email_success_logs),
            "emailErrorLogFound": bool(email_error_logs),
            "emailSuccessLogs": email_success_logs,
            "emailErrorLogs": email_error_logs,
            "note": "SES delivery requires a verified sender identity. If the account is in SES sandbox, the recipient must also be verified.",
        },
        "executionLogs": lambda_logs,
        "passed": bool(order_item and inventory_item and audit_result and email_success_logs),
    }
    save_evidence("case2-complete-order-flow", evidence)
    return evidence


def metric_statistics(config: dict[str, Any], profile: str | None, namespace: str, metric_name: str, dimensions: list[dict[str, str]], stat: str = "Sum") -> Any:
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(minutes=30)
    args = [
        "cloudwatch",
        "get-metric-statistics",
        "--namespace",
        namespace,
        "--metric-name",
        metric_name,
        "--start-time",
        start.isoformat(),
        "--end-time",
        end.isoformat(),
        "--period",
        "300",
        "--statistics",
        stat,
        "--dimensions",
        json.dumps(dimensions),
    ]
    return aws_cli(args, profile, config["region"], check=False)


def case_cloudwatch_monitoring(config: dict[str, Any]) -> dict[str, Any]:
    _, admin_profile = get_credentials(config, "admin")
    lambdas = config["lambdas"]
    api_names = config["apiNames"]
    stage = config["stageName"]
    dashboard_name = config.get("observability", {}).get("dashboardName", "cloudshop-observabilidad")

    lambda_name = lambdas["orders"]
    api_name = api_names["pedidos"]
    lambda_logs = filter_logs(config, admin_profile, config["logGroups"]["orders"], minutes=60)
    lambda_errors = metric_statistics(config, admin_profile, "AWS/Lambda", "Errors", [{"Name": "FunctionName", "Value": lambda_name}])
    api_requests = metric_statistics(
        config,
        admin_profile,
        "AWS/ApiGateway",
        "Count",
        [{"Name": "ApiName", "Value": api_name}, {"Name": "Stage", "Value": stage}],
    )
    api_5xx = metric_statistics(
        config,
        admin_profile,
        "AWS/ApiGateway",
        "5XXError",
        [{"Name": "ApiName", "Value": api_name}, {"Name": "Stage", "Value": stage}],
    )
    dashboard = aws_cli(["cloudwatch", "get-dashboard", "--dashboard-name", dashboard_name], admin_profile, config["region"], check=False)
    alarms = aws_cli(["cloudwatch", "describe-alarms", "--alarm-name-prefix", "cloudshop"], admin_profile, config["region"], check=False)

    evidence = {
        "case": "CloudWatch Monitoring",
        "timestamp": utc_now(),
        "lambdaLogs": lambda_logs,
        "apiGatewayMetrics": {"requests": api_requests, "fiveXx": api_5xx},
        "errorMetrics": {"lambdaErrors": lambda_errors},
        "dashboardMetrics": dashboard,
        "alarmStatus": alarms,
        "passed": bool(dashboard.get("DashboardBody") and alarms.get("MetricAlarms") is not None),
    }
    save_evidence("case3-cloudwatch-monitoring", evidence)
    return evidence


def case_terraform_deployment(config: dict[str, Any], apply: bool = False) -> dict[str, Any]:
    terraform_dir = pathlib.Path(config["terraformDirectory"])
    steps = []
    commands = [
        ["terraform", "fmt", "-recursive", "-check"],
        ["terraform", "init"],
        ["terraform", "validate"],
        ["terraform", "plan", "-out", "cloudshop.tfplan"],
    ]
    if apply:
        commands.append(["terraform", "apply", "-auto-approve", "cloudshop.tfplan"])

    for command in commands:
        result = run(command, cwd=terraform_dir, check=False)
        steps.append({"command": command, "returnCode": result.returncode, "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode != 0:
            break
    outputs = terraform_outputs(terraform_dir)
    evidence = {
        "case": "Terraform Deployment",
        "timestamp": utc_now(),
        "applyExecuted": apply,
        "steps": steps,
        "outputs": outputs,
        "passed": all(step["returnCode"] == 0 for step in steps),
    }
    save_evidence("case4-terraform-deployment", evidence)
    if not evidence["passed"]:
        raise IntegrationError("Terraform deployment verification failed. See evidence file for command output.")
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser(description="Run CloudShop Enterprise mandatory integration cases.")
    parser.add_argument("--config", default=str(pathlib.Path(__file__).resolve().parent / "cloudshop-test-config.example.json"))
    parser.add_argument("--case", choices=["all", "case1", "case2", "case3", "case4"], default="all")
    parser.add_argument("--apply", action="store_true", help="Allow case4 to run terraform apply.")
    args = parser.parse_args()

    config = merge_outputs(load_config(pathlib.Path(args.config)))
    cases = {
        "case1": lambda: case_unauthorized_access(config),
        "case2": lambda: case_complete_order_flow(config),
        "case3": lambda: case_cloudwatch_monitoring(config),
        "case4": lambda: case_terraform_deployment(config, args.apply),
    }
    selected = list(cases) if args.case == "all" else [args.case]
    summary = []
    try:
        for case_name in selected:
            print(f"Running {case_name}...")
            result = cases[case_name]()
            summary.append({"case": case_name, "passed": result.get("passed", False)})
            print(json.dumps(summary[-1], indent=2))
        save_evidence("summary", summary)
        return 0 if all(item["passed"] for item in summary) else 1
    except IntegrationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        save_evidence("failure", {"timestamp": utc_now(), "error": str(exc), "summary": summary})
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
