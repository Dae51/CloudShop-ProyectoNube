import json
import logging
import os
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


SES_SOURCE_EMAIL = os.environ.get("SES_SOURCE_EMAIL", "no-reply@cloudshop.local")
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)
ses = boto3.client("ses")


def log_event(level, event_name, **details):
    getattr(LOGGER, level)(json.dumps({"event": event_name, **details}, ensure_ascii=False, default=str))


def money(value):
    amount = Decimal(str(value))
    return f"{amount:.2f}"


def lambda_handler(event, context):
    detail = event.get("detail") or {}
    order_id = detail.get("orderId", "UNKNOWN")
    destination = detail.get("customerEmail")
    if not destination:
        log_event("info", "order_email_skipped", requestId=context.aws_request_id, orderId=order_id, reason="missing_customer_email")
        return {"statusCode": 204}

    total = money(detail.get("total", 0))
    subject = f"Confirmacion de pedido {order_id}"
    body = (
        f"Gracias por comprar en CloudShop.\n\n"
        f"Pedido: {order_id}\n"
        f"Estado: {detail.get('status', 'PENDIENTE')}\n"
        f"Total: {total}\n\n"
        "Te avisaremos cuando el pedido avance al siguiente estado."
    )
    try:
        ses.send_email(
            Source=SES_SOURCE_EMAIL,
            Destination={"ToAddresses": [destination]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
    except ClientError as exc:
        error = exc.response.get("Error", {})
        log_event(
            "exception",
            "order_email_failed",
            requestId=context.aws_request_id,
            orderId=order_id,
            source=SES_SOURCE_EMAIL,
            destination=destination,
            errorCode=error.get("Code", "AWS_ERROR"),
            errorMessage=error.get("Message", "SES rejected the email request"),
        )
        raise
    log_event("info", "order_email_sent", requestId=context.aws_request_id, orderId=order_id, destination=destination)
    return {"statusCode": 200}
