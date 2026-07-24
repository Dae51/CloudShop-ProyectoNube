import { Sha256 } from "@aws-crypto/sha256-js";
import { HttpRequest } from "@aws-sdk/protocol-http";
import { SignatureV4 } from "@aws-sdk/signature-v4";

export class ApiError extends Error {
  constructor(status, code, message, correlationId) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.correlationId = correlationId;
  }
}

function queryObject(searchParams) {
  const query = {};
  for (const [key, value] of searchParams.entries()) {
    query[key] = key in query ? [].concat(query[key], value) : value;
  }
  return query;
}

export function errorFromResponse(status, payload, correlationId) {
  const error = payload?.error || {};
  return new ApiError(
    status,
    error.code || "HTTP_ERROR",
    error.message || `La API respondió ${status}`,
    error.correlationId || correlationId || ""
  );
}

export function createApiClient({ apiUrl, region, getCredentials, fetchImpl = fetch }) {
  if (!apiUrl || !region || typeof getCredentials !== "function") {
    throw new Error("El cliente API requiere URL, región y credenciales");
  }
  const base = apiUrl.endsWith("/") ? apiUrl : `${apiUrl}/`;

  return async function request(path, options = {}) {
    const method = (options.method || "GET").toUpperCase();
    const url = new URL(path.replace(/^\//, ""), base);
    const body = options.body === undefined ? undefined : JSON.stringify(options.body);
    const correlationId = crypto.randomUUID();
    const credentials = await getCredentials();
    const signer = new SignatureV4({
      credentials,
      region,
      service: "execute-api",
      sha256: Sha256
    });
    const unsigned = new HttpRequest({
      protocol: url.protocol,
      hostname: url.hostname,
      port: url.port || undefined,
      method,
      path: url.pathname,
      query: queryObject(url.searchParams),
      headers: {
        host: url.host,
        accept: "application/json",
        "x-correlation-id": correlationId,
        ...(body ? { "content-type": "application/json" } : {}),
        ...(options.headers || {})
      },
      body
    });
    const signed = await signer.sign(unsigned);
    const headers = { ...signed.headers };
    delete headers.host;
    const result = await fetchImpl(url, {
      method,
      headers,
      body,
      signal: options.signal
    });
    const text = result.status === 204 ? "" : await result.text();
    let payload = null;
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        throw new ApiError(
          result.status,
          "INVALID_RESPONSE",
          "La API devolvió una respuesta no válida",
          result.headers.get("x-correlation-id") || correlationId
        );
      }
    }
    if (!result.ok) {
      throw errorFromResponse(
        result.status,
        payload,
        result.headers.get("x-correlation-id") || correlationId
      );
    }
    return payload;
  };
}
