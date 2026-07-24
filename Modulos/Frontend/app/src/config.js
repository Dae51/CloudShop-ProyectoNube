const REQUIRED = [
  "region",
  "apiUrl",
  "userPoolId",
  "userPoolClientId",
  "identityPoolId"
];

export function loadConfig(source = window.CLOUDSHOP_CONFIG || {}) {
  const config = {
    region: source.region || import.meta.env.VITE_AWS_REGION || "",
    apiUrl: source.apiUrl || import.meta.env.VITE_API_URL || "",
    userPoolId: source.userPoolId || import.meta.env.VITE_USER_POOL_ID || "",
    userPoolClientId:
      source.userPoolClientId || import.meta.env.VITE_USER_POOL_CLIENT_ID || "",
    identityPoolId:
      source.identityPoolId || import.meta.env.VITE_IDENTITY_POOL_ID || ""
  };
  const missing = REQUIRED.filter((key) => !config[key]);
  if (missing.length) {
    throw new Error(`Configuración incompleta: ${missing.join(", ")}`);
  }
  return config;
}
