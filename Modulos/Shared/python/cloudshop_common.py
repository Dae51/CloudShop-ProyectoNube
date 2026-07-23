import base64
import json
import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal


ROLES = frozenset({"ADMINISTRADOR", "OPERADOR", "CLIENTE"})
ROLE_ALIASES = {
    "ADMIN": "ADMINISTRADOR",
    "ADMINISTRADOR": "ADMINISTRADOR",
    "OPERATOR": "OPERADOR",
    "OPERADOR": "OPERADOR",
    "CLIENT": "CLIENTE",
    "CLIENTE": "CLIENTE",
}
CORRELATION_HEADER = "X-Correlation-Id"
LOGGER = logging.getLogger()
LOGGER.setLevel(logging.INFO)


class ApiError(Exception):
    def __init__(self, status_code, code, message):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def utc_now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def json_default(value):
    if isinstance(value, Decimal):
        return int(value) if value % 1 == 0 else float(value)
    raise TypeError(f"Type {type(value).__name__} is not JSON serializable")


def log_event(level, event_name, correlation_id, **details):
    safe_details = {
        key: value
        for key, value in details.items()
        if key.lower() not in {"authorization", "token", "password", "secret", "email"}
    }
    getattr(LOGGER, level)(
        json.dumps(
            {
                "event": event_name,
                "correlationId": correlation_id,
                **safe_details,
            },
            ensure_ascii=False,
            default=str,
        )
    )


def _header(event, name):
    headers = event.get("headers") or {}
    lowered = name.lower()
    return next(
        (value for key, value in headers.items() if str(key).lower() == lowered),
        None,
    )


def correlation_id(event, context=None):
    candidate = _header(event, CORRELATION_HEADER)
    try:
        return str(uuid.UUID(str(candidate))) if candidate else str(uuid.uuid4())
    except (ValueError, TypeError, AttributeError):
        request_id = getattr(context, "aws_request_id", None)
        try:
            return str(uuid.UUID(str(request_id)))
        except (ValueError, TypeError, AttributeError):
            return str(uuid.uuid4())


def response(status_code, body=None, correlation=None):
    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Expose-Headers": CORRELATION_HEADER,
        CORRELATION_HEADER: correlation or str(uuid.uuid4()),
    }
    result = {"statusCode": status_code, "headers": headers}
    if status_code != 204:
        result["body"] = json.dumps(body or {}, ensure_ascii=False, default=json_default)
    return result


def error_response(error, correlation):
    return response(
        error.status_code,
        {
            "error": {
                "code": error.code,
                "message": error.message,
                "correlationId": correlation,
            }
        },
        correlation,
    )


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
    if not match:
        return None
    role_name = match.group(1)
    for token in reversed(re.split(r"[^A-Za-z]+", role_name.upper())):
        role = normalize_role(token)
        if role:
            return role
    return None


def _subject_from_provider(provider):
    if not provider:
        return None
    match = re.search(r":CognitoSignIn:([^,]+)$", provider)
    return match.group(1) if match else None


def identity_from_event(event):
    request_context = event.get("requestContext") or {}
    authorizer = request_context.get("authorizer") or {}
    request_identity = request_context.get("identity") or {}
    claims = authorizer.get("claims") or {}
    jwt_claims = (authorizer.get("jwt") or {}).get("claims") or {}

    candidates = (
        authorizer.get("role"),
        claims.get("custom:role"),
        claims.get("role"),
        claims.get("cognito:groups"),
        jwt_claims.get("custom:role"),
        jwt_claims.get("role"),
        jwt_claims.get("cognito:groups"),
    )
    role = next((normalize_role(value) for value in candidates if normalize_role(value)), None)
    user_arn = request_identity.get("userArn")
    role = role or role_from_iam_arn(user_arn)

    actor_id = (
        authorizer.get("principalId")
        or claims.get("sub")
        or jwt_claims.get("sub")
        or _subject_from_provider(request_identity.get("cognitoAuthenticationProvider"))
        or request_identity.get("cognitoIdentityId")
        or request_identity.get("user")
        or user_arn
    )
    customer_id = request_identity.get("cognitoIdentityId") or actor_id
    authenticated = bool(
        actor_id
        or request_identity.get("caller")
        or request_identity.get("accessKey")
    )
    return {
        "authenticated": authenticated,
        "role": role,
        "actor_id": actor_id or "UNKNOWN",
        "customer_id": customer_id or "UNKNOWN",
        "user_arn": user_arn,
    }


def require_role(event, allowed_roles):
    identity = identity_from_event(event)
    if not identity["authenticated"]:
        raise ApiError(401, "UNAUTHENTICATED", "Autenticación requerida")
    if identity["role"] not in set(allowed_roles):
        raise ApiError(403, "FORBIDDEN", "No tiene permisos para realizar esta acción")
    return identity


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


def required_text(body, field, max_length):
    value = body.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ApiError(400, "INVALID_INPUT", f"{field} es obligatorio")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise ApiError(
            400,
            "INVALID_INPUT",
            f"{field} no puede exceder {max_length} caracteres",
        )
    return normalized


def idempotency_key(event):
    value = _header(event, "Idempotency-Key")
    try:
        return str(uuid.UUID(str(value)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise ApiError(
            400,
            "INVALID_INPUT",
            "Idempotency-Key debe ser un UUID válido",
        ) from exc
