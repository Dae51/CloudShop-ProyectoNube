import { describe, expect, it } from "vitest";
import { decodeJwtPayload, deriveRole, homeForRole, ROLES } from "./roles";

function token(payload) {
  const encoded = btoa(unescape(encodeURIComponent(JSON.stringify(payload))))
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=+$/, "");
  return `header.${encoded}.signature`;
}

describe("roles oficiales", () => {
  it("acepta exactamente un grupo oficial", () => {
    expect(deriveRole({ "cognito:groups": ["CLIENTE"] })).toBe(ROLES.CLIENTE);
  });

  it("falla cerrado ante cero o múltiples roles", () => {
    expect(deriveRole({ "cognito:groups": [] })).toBeNull();
    expect(
      deriveRole({ "cognito:groups": ["CLIENTE", "ADMINISTRADOR"] })
    ).toBeNull();
    expect(deriveRole({ "cognito:groups": ["EJECUTIVO"] })).toBeNull();
  });

  it("decodifica payloads UTF-8 y dirige por rol", () => {
    expect(decodeJwtPayload(token({ name: "José", sub: "123" })).name).toBe("José");
    expect(homeForRole(ROLES.ADMINISTRADOR)).toBe("/admin/dashboard");
    expect(homeForRole(ROLES.OPERADOR)).toBe("/operador/pedidos");
    expect(homeForRole(ROLES.CLIENTE)).toBe("/productos");
  });
});
