import base64
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from botocore.exceptions import ClientError


PRODUCTS_TABLE = os.environ.get("PRODUCTS_TABLE", "Products")
AUDIT_TABLE = os.environ.get("AUDIT_TABLE", "ProductAudit")
STORE_INDEX = os.environ.get("STORE_INDEX", "StoreIdCreatedAtIndex")

LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)

SERIALIZER = TypeSerializer()
DESERIALIZER = TypeDeserializer()
_dynamodb_client = None

ROLE_ALIASES = {
    "ADMIN": "ADMINISTRADOR",
    "ADMINISTRADOR": "ADMINISTRADOR",
    "OPERATOR": "OPERADOR",
    "OPERADOR": "OPERADOR",
    "CLIENT": "CLIENTE",
    "CLIENTE": "CLIENTE",
}

PERMISSIONS = {
    "ADMINISTRADOR": {
        "CREATE",
        "LIST",
        "GET",
        "LIST_BY_STORE",
        "UPDATE",
        "UPDATE_INVENTORY",
        "DELETE",
    },
    "OPERADOR": {"LIST", "GET", "LIST_BY_STORE", "UPDATE_INVENTORY"},
    "CLIENTE": {"LIST", "GET", "LIST_BY_STORE"},
}

AUDIT_ACTIONS = {
    "CREATE": "CREATE_PRODUCT",
    "UPDATE": "UPDATE_PRODUCT",
    "UPDATE_INVENTORY": "UPDATE_PRODUCT_INVENTORY",
    "DELETE": "DELETE_PRODUCT",
}


class ApiError(Exception):
    def __init__(self, status_code, code, message):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def get_dynamodb_client():
    global _dynamodb_client
    if _dynamodb_client is None:
        _dynamodb_client = boto3.client("dynamodb")
    return _dynamodb_client


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def log_event(level, event_name, **details):
    getattr(LOGGER, level)(
        json.dumps({"event": event_name, **details}, ensure_ascii=False, default=str)
    )


def json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Type {type(value).__name__} is not JSON serializable")


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
        },
        "body": json.dumps(body, ensure_ascii=False, default=json_default),
    }


def error_response(status_code, code, message):
    return response(status_code, {"error": {"code": code, "message": message}})


def serialize_item(item):
    return {key: SERIALIZER.serialize(value) for key, value in item.items()}


def deserialize_item(item):
    return {key: DESERIALIZER.deserialize(value) for key, value in item.items()}


def normalize_role(raw_role):
    if isinstance(raw_role, list):
        raw_role = raw_role[0] if raw_role else None
    if not raw_role:
        return None
    if isinstance(raw_role, str) and raw_role.startswith("["):
        try:
            groups = json.loads(raw_role)
            raw_role = groups[0] if groups else None
        except json.JSONDecodeError:
            pass
    if not raw_role:
        return None
    normalized = str(raw_role).strip().upper()
    if "," in normalized:
        normalized = normalized.split(",", 1)[0].strip()
    return ROLE_ALIASES.get(normalized)


def role_from_iam_arn(user_arn):
    if not user_arn:
        return None
    match = re.search(r"(?:assumed-role|role)/([^/]+)", user_arn, re.IGNORECASE)
    role_name = match.group(1) if match else user_arn.rsplit("/", 1)[-1]
    tokens = re.split(r"[^A-Za-z]+", role_name.upper())
    for token in reversed(tokens):
        role = normalize_role(token)
        if role:
            return role
    return None


def get_identity(event):
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    identity = request_context.get("identity") or {}
    claims = authorizer.get("claims") or {}
    jwt_claims = (authorizer.get("jwt") or {}).get("claims") or {}

    role_candidates = [
        authorizer.get("role"),
        claims.get("custom:role"),
        claims.get("role"),
        claims.get("cognito:groups"),
        jwt_claims.get("custom:role"),
        jwt_claims.get("role"),
        jwt_claims.get("cognito:groups"),
    ]
    role = None
    for candidate in role_candidates:
        role = normalize_role(candidate)
        if role:
            break
    user_arn = identity.get("userArn")
    role = role or role_from_iam_arn(user_arn)

    user_id = (
        authorizer.get("principalId")
        or claims.get("sub")
        or claims.get("cognito:username")
        or jwt_claims.get("sub")
        or identity.get("user")
        or user_arn
    )
    authenticated = bool(user_id or identity.get("caller"))
    return {"authenticated": authenticated, "role": role, "user_id": user_id or "UNKNOWN"}


def route_action(event):
    method = (event.get("httpMethod") or "").upper()
    resource = event.get("resource") or event.get("path") or ""

    if resource == "/productos" and method == "POST":
        return "CREATE"
    if resource == "/productos" and method == "GET":
        return "LIST"
    if resource == "/productos/{productId}" and method == "GET":
        return "GET"
    if resource == "/productos/{productId}" and method == "PUT":
        return "UPDATE"
    if resource == "/productos/{productId}" and method == "DELETE":
        return "DELETE"
    if resource == "/productos/{productId}/inventario" and method == "PATCH":
        return "UPDATE_INVENTORY"
    if resource == "/tiendas/{storeId}/productos" and method == "GET":
        return "LIST_BY_STORE"
    raise ApiError(404, "ROUTE_NOT_FOUND", "Ruta no encontrada")


def parse_body(event):
    raw_body = event.get("body")
    if raw_body is None:
        raise ApiError(400, "INVALID_INPUT", "El cuerpo de la solicitud es obligatorio")
    if event.get("isBase64Encoded"):
        try:
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise ApiError(400, "INVALID_INPUT", "El cuerpo codificado no es válido") from exc
    try:
        body = json.loads(raw_body) if isinstance(raw_body, str) else raw_body
    except json.JSONDecodeError as exc:
        raise ApiError(400, "INVALID_JSON", "El cuerpo debe contener JSON válido") from exc
    if not isinstance(body, dict):
        raise ApiError(400, "INVALID_INPUT", "El cuerpo debe ser un objeto JSON")
    return body


def required_text(body, field):
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "INVALID_INPUT", f"{field} es obligatorio")
    return value.strip()


def parse_price(value):
    if isinstance(value, bool):
        raise ApiError(400, "INVALID_INPUT", "price debe ser un número mayor que 0")
    try:
        price = Decimal(str(value))
    except Exception as exc:
        raise ApiError(400, "INVALID_INPUT", "price debe ser un número mayor que 0") from exc
    if not price.is_finite() or price <= 0:
        raise ApiError(400, "INVALID_INPUT", "price debe ser un número mayor que 0")
    return price


def parse_inventory(value):
    if isinstance(value, bool):
        raise ApiError(400, "INVALID_INPUT", "inventory debe ser un entero mayor o igual que 0")
    try:
        inventory = int(value)
    except (TypeError, ValueError) as exc:
        raise ApiError(400, "INVALID_INPUT", "inventory debe ser un entero mayor o igual que 0") from exc
    if inventory < 0 or isinstance(value, float) and not value.is_integer():
        raise ApiError(400, "INVALID_INPUT", "inventory debe ser un entero mayor o igual que 0")
    if isinstance(value, str) and str(inventory) != value.strip():
        raise ApiError(400, "INVALID_INPUT", "inventory debe ser un entero mayor o igual que 0")
    return inventory


def validate_product(body):
    return {
        "code": required_text(body, "code"),
        "name": required_text(body, "name"),
        "description": required_text(body, "description"),
        "category": required_text(body, "category"),
        "price": parse_price(body.get("price")),
        "inventory": parse_inventory(body.get("inventory")),
        "storeId": required_text(body, "storeId"),
    }


def get_product(product_id, include_deleted=False):
    result = get_dynamodb_client().get_item(
        TableName=PRODUCTS_TABLE,
        Key={"productId": {"S": product_id}},
        ConsistentRead=True,
    )
    raw_item = result.get("Item")
    if not raw_item:
        raise ApiError(404, "PRODUCT_NOT_FOUND", "El producto no existe")
    product = deserialize_item(raw_item)
    if product.get("status") == "DELETED" and not include_deleted:
        raise ApiError(404, "PRODUCT_NOT_FOUND", "El producto no existe")
    return product


def build_audit(identity, action, product_id, result="EXITOSO"):
    return {
        "auditId": str(uuid.uuid4()),
        "usuario": identity["user_id"],
        "accion": AUDIT_ACTIONS[action],
        "resourceType": "PRODUCT",
        "resourceId": product_id,
        "fecha": utc_now(),
        "resultado": result,
    }


def transact_product_and_audit(product, previous_updated_at, audit):
    condition = "attribute_not_exists(productId)"
    names = None
    values = None
    if previous_updated_at is not None:
        condition = "attribute_exists(productId) AND #status = :active AND updatedAt = :previous"
        names = {"#status": "status"}
        values = {
            ":active": {"S": "ACTIVE"},
            ":previous": {"S": previous_updated_at},
        }

    product_put = {
        "TableName": PRODUCTS_TABLE,
        "Item": serialize_item(product),
        "ConditionExpression": condition,
    }
    if names:
        product_put["ExpressionAttributeNames"] = names
        product_put["ExpressionAttributeValues"] = values

    get_dynamodb_client().transact_write_items(
        TransactItems=[
            {"Put": product_put},
            {"Put": {"TableName": AUDIT_TABLE, "Item": serialize_item(audit)}},
        ]
    )


def write_failed_audit(identity, action, product_id):
    if action not in AUDIT_ACTIONS:
        return
    try:
        audit = build_audit(identity, action, product_id or "UNKNOWN", "FALLIDO")
        get_dynamodb_client().put_item(TableName=AUDIT_TABLE, Item=serialize_item(audit))
    except Exception:
        log_event("exception", "audit_write_failed", action=action, productId=product_id)


def create_product(event, identity):
    body = validate_product(parse_body(event))
    timestamp = utc_now()
    product = {
        "productId": str(uuid.uuid4()),
        **body,
        "status": "ACTIVE",
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    audit = build_audit(identity, "CREATE", product["productId"])
    transact_product_and_audit(product, None, audit)
    log_event("info", "product_created", productId=product["productId"], usuario=identity["user_id"])
    return response(201, {"data": product})


def list_products(event, identity):
    params = event.get("queryStringParameters") or {}
    include_deleted = str(params.get("includeDeleted", "false")).lower() == "true"
    if include_deleted and identity["role"] != "ADMINISTRADOR":
        raise ApiError(403, "FORBIDDEN", "No tiene permisos para consultar productos eliminados")

    request = {"TableName": PRODUCTS_TABLE}
    if not include_deleted:
        request.update(
            {
                "FilterExpression": "#status = :active",
                "ExpressionAttributeNames": {"#status": "status"},
                "ExpressionAttributeValues": {":active": {"S": "ACTIVE"}},
            }
        )
    result = get_dynamodb_client().scan(**request)
    items = [deserialize_item(item) for item in result.get("Items", [])]
    return response(200, {"data": items, "count": len(items)})


def get_product_response(event, identity):
    product_id = (event.get("pathParameters") or {}).get("productId")
    if not product_id:
        raise ApiError(400, "INVALID_INPUT", "productId es obligatorio")
    params = event.get("queryStringParameters") or {}
    include_deleted = str(params.get("includeDeleted", "false")).lower() == "true"
    if include_deleted and identity["role"] != "ADMINISTRADOR":
        raise ApiError(403, "FORBIDDEN", "No tiene permisos para consultar productos eliminados")
    return response(200, {"data": get_product(product_id, include_deleted)})


def list_products_by_store(event, identity):
    store_id = (event.get("pathParameters") or {}).get("storeId")
    if not store_id:
        raise ApiError(400, "INVALID_INPUT", "storeId es obligatorio")
    result = get_dynamodb_client().query(
        TableName=PRODUCTS_TABLE,
        IndexName=STORE_INDEX,
        KeyConditionExpression="storeId = :store_id",
        FilterExpression="#status = :active",
        ExpressionAttributeNames={"#status": "status"},
        ExpressionAttributeValues={
            ":store_id": {"S": store_id},
            ":active": {"S": "ACTIVE"},
        },
    )
    items = [deserialize_item(item) for item in result.get("Items", [])]
    return response(200, {"data": items, "count": len(items)})


def update_product(event, identity):
    product_id = (event.get("pathParameters") or {}).get("productId")
    if not product_id:
        raise ApiError(400, "INVALID_INPUT", "productId es obligatorio")
    values = validate_product(parse_body(event))
    current = get_product(product_id)
    updated = {**current, **values, "updatedAt": utc_now()}
    audit = build_audit(identity, "UPDATE", product_id)
    transact_product_and_audit(updated, current["updatedAt"], audit)
    log_event("info", "product_updated", productId=product_id, usuario=identity["user_id"])
    return response(200, {"data": updated})


def update_inventory(event, identity):
    product_id = (event.get("pathParameters") or {}).get("productId")
    if not product_id:
        raise ApiError(400, "INVALID_INPUT", "productId es obligatorio")
    body = parse_body(event)
    if "inventory" not in body:
        raise ApiError(400, "INVALID_INPUT", "inventory es obligatorio")
    inventory = parse_inventory(body["inventory"])
    current = get_product(product_id)
    updated = {**current, "inventory": inventory, "updatedAt": utc_now()}
    audit = build_audit(identity, "UPDATE_INVENTORY", product_id)
    transact_product_and_audit(updated, current["updatedAt"], audit)
    log_event("info", "product_inventory_updated", productId=product_id, usuario=identity["user_id"])
    return response(200, {"data": updated})


def delete_product(event, identity):
    product_id = (event.get("pathParameters") or {}).get("productId")
    if not product_id:
        raise ApiError(400, "INVALID_INPUT", "productId es obligatorio")
    current = get_product(product_id)
    deleted = {**current, "status": "DELETED", "updatedAt": utc_now()}
    audit = build_audit(identity, "DELETE", product_id)
    transact_product_and_audit(deleted, current["updatedAt"], audit)
    log_event("info", "product_deleted", productId=product_id, usuario=identity["user_id"])
    return response(200, {"data": deleted})


HANDLERS = {
    "CREATE": create_product,
    "LIST": list_products,
    "GET": get_product_response,
    "LIST_BY_STORE": list_products_by_store,
    "UPDATE": update_product,
    "UPDATE_INVENTORY": update_inventory,
    "DELETE": delete_product,
}


def lambda_handler(event, context):
    request_id = getattr(context, "aws_request_id", None)
    action = None
    identity = {"authenticated": False, "role": None, "user_id": "UNKNOWN"}
    product_id = (event.get("pathParameters") or {}).get("productId")
    try:
        identity = get_identity(event)
        if not identity["authenticated"] or identity["role"] not in PERMISSIONS:
            raise ApiError(403, "FORBIDDEN", "Autenticación o rol inválido")
        action = route_action(event)
        if action not in PERMISSIONS[identity["role"]]:
            raise ApiError(403, "FORBIDDEN", "No tiene permisos para realizar esta acción")

        log_event(
            "info",
            "product_request",
            requestId=request_id,
            action=action,
            role=identity["role"],
            usuario=identity["user_id"],
        )
        return HANDLERS[action](event, identity)
    except ApiError as exc:
        if action in AUDIT_ACTIONS:
            write_failed_audit(identity, action, product_id)
        log_event(
            "warning",
            "product_request_rejected",
            requestId=request_id,
            action=action,
            statusCode=exc.status_code,
            errorCode=exc.code,
        )
        return error_response(exc.status_code, exc.code, exc.message)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code", "DYNAMODB_ERROR")
        if action in AUDIT_ACTIONS:
            write_failed_audit(identity, action, product_id)
        log_event(
            "exception",
            "product_dynamodb_error",
            requestId=request_id,
            action=action,
            errorCode=error_code,
        )
        if error_code in {"ConditionalCheckFailedException", "TransactionCanceledException"}:
            return error_response(409, "CONCURRENT_MODIFICATION", "El producto fue modificado; intente nuevamente")
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
    except Exception:
        if action in AUDIT_ACTIONS:
            write_failed_audit(identity, action, product_id)
        log_event("exception", "product_unexpected_error", requestId=request_id, action=action)
        return error_response(500, "INTERNAL_ERROR", "Error interno del servidor")
