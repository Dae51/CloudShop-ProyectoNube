import { describe, expect, it, vi } from "vitest";
import { createApiClient, errorFromResponse } from "./client";

const credentials = {
  accessKeyId: "AKIATEST",
  secretAccessKey: "secret",
  sessionToken: "session"
};

describe("cliente SigV4", () => {
  it("firma métodos con cuerpo e incluye correlación", async () => {
    const fetchImpl = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: { ok: true } }), {
        status: 200,
        headers: { "content-type": "application/json" }
      })
    );
    const request = createApiClient({
      apiUrl: "https://example.execute-api.us-east-2.amazonaws.com/prod",
      region: "us-east-2",
      getCredentials: async () => credentials,
      fetchImpl
    });

    await expect(
      request("/carritos/mio/items", {
        method: "POST",
        body: { productId: "p1", quantity: 1 }
      })
    ).resolves.toEqual({ data: { ok: true } });

    const [, options] = fetchImpl.mock.calls[0];
    expect(options.method).toBe("POST");
    expect(options.body).toBe('{"productId":"p1","quantity":1}');
    expect(options.headers.authorization).toMatch(/^AWS4-HMAC-SHA256 /);
    expect(options.headers["x-amz-security-token"]).toBe("session");
    expect(options.headers["x-correlation-id"]).toBeTruthy();
  });

  it("conserva estado, código y correlación de errores API", () => {
    const error = errorFromResponse(
      403,
      { error: { code: "FORBIDDEN", message: "Sin permiso", correlationId: "corr-1" } },
      "corr-2"
    );
    expect(error).toMatchObject({
      status: 403,
      code: "FORBIDDEN",
      message: "Sin permiso",
      correlationId: "corr-1"
    });
  });

  it("no convierte respuestas inválidas en datos demo", async () => {
    const request = createApiClient({
      apiUrl: "https://example.execute-api.us-east-2.amazonaws.com/prod",
      region: "us-east-2",
      getCredentials: async () => credentials,
      fetchImpl: vi.fn().mockResolvedValue(new Response("<html>error</html>", { status: 502 }))
    });
    await expect(request("/productos")).rejects.toMatchObject({
      code: "INVALID_RESPONSE",
      status: 502
    });
  });
});
