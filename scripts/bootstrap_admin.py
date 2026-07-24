#!/usr/bin/env python3
"""Promueve exactamente al primer ADMINISTRADOR con compensación y auditoría."""

import argparse
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError


SERIALIZER = TypeSerializer()


def arguments():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile")
    parser.add_argument("--region", required=True)
    parser.add_argument("--expected-account", required=True)
    parser.add_argument("--user-pool-id", required=True)
    parser.add_argument("--users-table", required=True)
    parser.add_argument("--audit-table", required=True)
    parser.add_argument("--username", required=True)
    return parser.parse_args()


def attribute(attributes, name):
    return next((item["Value"] for item in attributes if item["Name"] == name), None)


def main():
    args = arguments()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    sts = session.client("sts")
    cognito = session.client("cognito-idp")
    dynamodb = session.client("dynamodb")
    caller = sts.get_caller_identity()
    if caller["Account"] != args.expected_account:
        raise SystemExit("BLOCKED: la cuenta AWS no coincide con --expected-account")

    user = cognito.admin_get_user(
        UserPoolId=args.user_pool_id,
        Username=args.username,
    )
    user_id = attribute(user["UserAttributes"], "sub")
    if not user_id:
        raise SystemExit("BLOCKED: el usuario Cognito no tiene atributo sub")
    if not user.get("Enabled") or user.get("UserStatus") != "CONFIRMED":
        raise SystemExit("BLOCKED: el usuario Cognito debe estar habilitado y CONFIRMED")

    stored = dynamodb.get_item(
        TableName=args.users_table,
        Key={"userId": {"S": user_id}},
        ConsistentRead=True,
    ).get("Item")
    current_groups = {
        item["GroupName"]
        for item in cognito.admin_list_groups_for_user(
            UserPoolId=args.user_pool_id,
            Username=args.username,
        ).get("Groups", [])
    }
    existing_admins = cognito.list_users_in_group(
        UserPoolId=args.user_pool_id,
        GroupName="ADMINISTRADOR",
        Limit=2,
    ).get("Users", [])
    if existing_admins:
        names = {item["Username"] for item in existing_admins}
        if args.username not in names or len(names) != 1:
            raise SystemExit("BLOCKED: ya existe un ADMINISTRADOR diferente")
        if (
            not stored
            or stored.get("role", {}).get("S") != "ADMINISTRADOR"
            or stored.get("status", {}).get("S") != "ACTIVE"
            or current_groups != {"ADMINISTRADOR"}
        ):
            raise SystemExit(
                "BLOCKED: el administrador existente está desincronizado"
            )
        print("PASS: el administrador inicial ya existe; no se hicieron cambios")
        return

    if (
        not stored
        or stored.get("role", {}).get("S") != "CLIENTE"
        or stored.get("status", {}).get("S") != "ACTIVE"
        or current_groups != {"CLIENTE"}
    ):
        raise SystemExit(
            "BLOCKED: Cognito/Users debe contener exactamente un CLIENTE ACTIVE"
        )

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    correlation = str(uuid.uuid4())
    audit = {
        "auditId": str(uuid.uuid4()),
        "actorId": caller["Arn"],
        "action": "BOOTSTRAP_ADMIN_ROLE",
        "resourceType": "USER",
        "resourceId": user_id,
        "resourceKey": f"USER#{user_id}",
        "occurredAt": timestamp,
        "result": "EXITOSO",
        "correlationId": correlation,
    }

    cognito.admin_add_user_to_group(
        UserPoolId=args.user_pool_id,
        Username=args.username,
        GroupName="ADMINISTRADOR",
    )
    try:
        cognito.admin_remove_user_from_group(
            UserPoolId=args.user_pool_id,
            Username=args.username,
            GroupName="CLIENTE",
        )
        dynamodb.transact_write_items(
            TransactItems=[
                {
                    "Update": {
                        "TableName": args.users_table,
                        "Key": {"userId": {"S": user_id}},
                        "UpdateExpression": "SET #role = :admin, updatedAt = :updated",
                        "ConditionExpression": "#role = :client AND #status = :active",
                        "ExpressionAttributeNames": {
                            "#role": "role",
                            "#status": "status",
                        },
                        "ExpressionAttributeValues": {
                            ":admin": {"S": "ADMINISTRADOR"},
                            ":client": {"S": "CLIENTE"},
                            ":active": {"S": "ACTIVE"},
                            ":updated": {"S": timestamp},
                        },
                    }
                },
                {
                    "Put": {
                        "TableName": args.audit_table,
                        "Item": {
                            key: SERIALIZER.serialize(value)
                            for key, value in audit.items()
                        },
                    }
                },
            ]
        )
    except Exception:
        try:
            cognito.admin_remove_user_from_group(
                UserPoolId=args.user_pool_id,
                Username=args.username,
                GroupName="ADMINISTRADOR",
            )
            cognito.admin_add_user_to_group(
                UserPoolId=args.user_pool_id,
                Username=args.username,
                GroupName="CLIENTE",
            )
        except ClientError:
            pass
        raise

    print(f"PASS: primer ADMINISTRADOR creado y auditado; correlationId={correlation}")


if __name__ == "__main__":
    main()
