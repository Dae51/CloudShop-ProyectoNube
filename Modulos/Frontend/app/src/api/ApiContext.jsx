import { createContext, useContext, useMemo } from "react";
import { useAuth } from "../auth/AuthContext";
import { createApiClient } from "./client";

const ApiContext = createContext(null);

export function ApiProvider({ children }) {
  const { config, getCredentials } = useAuth();
  const request = useMemo(
    () =>
      createApiClient({
        apiUrl: config.apiUrl,
        region: config.region,
        getCredentials
      }),
    [config.apiUrl, config.region, getCredentials]
  );
  return <ApiContext.Provider value={request}>{children}</ApiContext.Provider>;
}

export function useApi() {
  const request = useContext(ApiContext);
  if (!request) throw new Error("useApi requiere ApiProvider");
  return request;
}
