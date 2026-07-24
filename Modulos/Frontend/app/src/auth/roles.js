export const ROLES = Object.freeze({
  ADMINISTRADOR: "ADMINISTRADOR",
  OPERADOR: "OPERADOR",
  CLIENTE: "CLIENTE"
});

const OFFICIAL = new Set(Object.values(ROLES));

export function deriveRole(payload = {}) {
  const groups = payload["cognito:groups"];
  if (!Array.isArray(groups)) return null;
  const official = groups.filter((group) => OFFICIAL.has(group));
  return official.length === 1 ? official[0] : null;
}

export function decodeJwtPayload(token) {
  const part = token?.split(".")[1];
  if (!part) throw new Error("Token de identidad inválido");
  const normalized = part.replace(/-/g, "+").replace(/_/g, "/");
  const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, "=");
  const bytes = Uint8Array.from(atob(padded), (character) =>
    character.charCodeAt(0)
  );
  return JSON.parse(new TextDecoder().decode(bytes));
}

export function homeForRole(role) {
  if (role === ROLES.ADMINISTRADOR) return "/admin/dashboard";
  if (role === ROLES.OPERADOR) return "/operador/pedidos";
  return "/productos";
}
