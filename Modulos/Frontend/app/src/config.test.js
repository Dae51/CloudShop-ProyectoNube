import { describe, expect, it } from "vitest";
import { loadConfig } from "./config";

const complete = {
  region: "us-east-2",
  apiUrl: "https://example.execute-api.us-east-2.amazonaws.com/prod",
  userPoolId: "us-east-2_example",
  userPoolClientId: "client",
  identityPoolId: "us-east-2:identity"
};

describe("configuración de runtime", () => {
  it("carga una configuración completa", () => {
    expect(loadConfig(complete)).toEqual(complete);
  });

  it("falla explícitamente sin integración real", () => {
    expect(() => loadConfig({})).toThrow(/Configuración incompleta/);
  });
});
