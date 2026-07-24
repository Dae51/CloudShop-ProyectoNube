import json
import logging
import os
import uuid
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.types import TypeSerializer
from botocore.exceptions import ClientError


USERS_TABLE = os.environ["USERS_TABLE"]
AUDIT_TABLE = os.environ["AUDIT_TABLE"]
CLIENT_GROUP = "CLIENTE"
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
SERIALIZER = TypeSerializer()
_dynamodb = None
_cognito = None


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def clients():
    global _dynamodb, _cognito
    if _dynamodb is None:
        _dynamodb = boto3.client("dynamodb")
    if _cognito is None:
        _cognito = boto3.client("cognito-idp")
    return _dynamodb, _cognito


def _handle(event, context):
    attributes = event["request"]["userAttributes"]
    user_id = attributes["sub"]
    timestamp = utc_now()
    correlation_id = getattr(context, "aws_request_id", None) or str(uuid.uuid4())
    dynamodb, cognito = clients()

    # El grupo no proviene del formulario ni de un custom attribute escribible.
    cognito.admin_add_user_to_group(
        UserPoolId=event["userPoolId"],
        Username=event["userName"],
        GroupName=CLIENT_GROUP,
    )

    user = {
        "userId": user_id,
        "username": event["userName"],
        "name": attributes.get("name") or event["userName"],
        "email": attributes["email"].lower(),
        "role": CLIENT_GROUP,
        "status": "ACTIVE",
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    audit = {
        "auditId": str(uuid.uuid4()),
        "actorId": user_id,
        "action": "CREATE_USER",
        "resourceType": "USER",
        "resourceId": user_id,
        "resourceKey": f"USER#{user_id}",
        "occurredAt": timestamp,
        "result": "EXITOSO",
        "correlationId": correlation_id,
    }

    try:
        dynamodb.transact_write_items(
            TransactItems=[
                {
                    "Put": {
                        "TableName": USERS_TABLE,
                        "Item": serialize(user),
                        "ConditionExpression": "attribute_not_exists(userId)",
                    }
                },
                {"Put": {"TableName": AUDIT_TABLE, "Item": serialize(audit)}},
            ]
        )
        outcome = "created"
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code")
        if code != "TransactionCanceledException":
            raise
        existing = dynamodb.get_item(
            TableName=USERS_TABLE,
            Key={"userId": {"S": user_id}},
            ConsistentRead=True,
        )
        if "Item" not in existing:
            raise
        outcome = "already_exists"

    LOGGER.info(
        json.dumps(
            {
                "event": "user_post_confirmation",
                "correlationId": correlation_id,
                "userId": user_id,
                "role": CLIENT_GROUP,
                "outcome": outcome,
            }
        )
    )
    return event


def lambda_handler(event, context):
    correlation_id = getattr(context, "aws_request_id", None) or str(uuid.uuid4())
    try:
        return _handle(event, context)
    except Exception as exc:
        LOGGER.exception(
            json.dumps(
                {
                    "event": "user_post_confirmation_failed",
                    "correlationId": correlation_id,
                    "statusCode": 500,
                    "errorCode": type(exc).__name__,
                }
            )
        )
        raise
