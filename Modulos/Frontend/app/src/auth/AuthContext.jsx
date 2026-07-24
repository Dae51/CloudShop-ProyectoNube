import {
  AuthenticationDetails,
  CognitoUser,
  CognitoUserAttribute,
  CognitoUserPool
} from "amazon-cognito-identity-js";
import { CognitoIdentityClient } from "@aws-sdk/client-cognito-identity";
import { fromCognitoIdentityPool } from "@aws-sdk/credential-provider-cognito-identity";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState
} from "react";
import { loadConfig } from "../config";
import { decodeJwtPayload, deriveRole } from "./roles";

const AuthContext = createContext(null);

function asPromise(action) {
  return new Promise((resolve, reject) => action(resolve, reject));
}

export function AuthProvider({ children }) {
  const config = useMemo(() => loadConfig(), []);
  const pool = useMemo(
    () =>
      new CognitoUserPool({
        UserPoolId: config.userPoolId,
        ClientId: config.userPoolClientId
      }),
    [config.userPoolClientId, config.userPoolId]
  );
  const [session, setSession] = useState(null);
  const [status, setStatus] = useState("loading");
  const [authError, setAuthError] = useState("");
  const credentialsRef = useRef(null);

  const applySession = useCallback((nextSession) => {
    const token = nextSession.getIdToken().getJwtToken();
    const payload = decodeJwtPayload(token);
    const role = deriveRole(payload);
    if (!role) {
      throw new Error("La cuenta no tiene exactamente un rol oficial");
    }
    setSession({
      cognitoSession: nextSession,
      idToken: token,
      userId: payload.sub,
      email: payload.email,
      name: payload.name || payload.email,
      role
    });
    credentialsRef.current = null;
    setAuthError("");
    setStatus("authenticated");
  }, []);

  useEffect(() => {
    const user = pool.getCurrentUser();
    if (!user) {
      setStatus("anonymous");
      return;
    }
    user.getSession((error, currentSession) => {
      if (error || !currentSession?.isValid()) {
        setSession(null);
        setStatus("anonymous");
        return;
      }
      try {
        applySession(currentSession);
      } catch (sessionError) {
        setAuthError(sessionError.message);
        setStatus("anonymous");
      }
    });
  }, [applySession, pool]);

  const login = useCallback(
    async (email, password) => {
      setAuthError("");
      const user = new CognitoUser({ Username: email.trim(), Pool: pool });
      const details = new AuthenticationDetails({
        Username: email.trim(),
        Password: password
      });
      const nextSession = await asPromise((resolve, reject) =>
        user.authenticateUser(details, {
          onSuccess: resolve,
          onFailure: reject,
          newPasswordRequired: () =>
            reject(new Error("La cuenta requiere cambio administrativo de contraseña"))
        })
      );
      applySession(nextSession);
      return nextSession;
    },
    [applySession, pool]
  );

  const register = useCallback(
    (name, email, password) =>
      asPromise((resolve, reject) => {
        const attributes = [
          new CognitoUserAttribute({ Name: "name", Value: name.trim() }),
          new CognitoUserAttribute({
            Name: "email",
            Value: email.trim().toLowerCase()
          })
        ];
        pool.signUp(
          email.trim().toLowerCase(),
          password,
          attributes,
          null,
          (error, result) => (error ? reject(error) : resolve(result))
        );
      }),
    [pool]
  );

  const confirmRegistration = useCallback(
    (email, code) => {
      const user = new CognitoUser({ Username: email.trim(), Pool: pool });
      return asPromise((resolve, reject) =>
        user.confirmRegistration(code.trim(), true, (error, result) =>
          error ? reject(error) : resolve(result)
        )
      );
    },
    [pool]
  );

  const logout = useCallback(() => {
    pool.getCurrentUser()?.signOut();
    credentialsRef.current = null;
    setSession(null);
    setStatus("anonymous");
  }, [pool]);

  const getCredentials = useCallback(async () => {
    if (!session?.idToken) throw new Error("Sesión no disponible");
    if (!credentialsRef.current) {
      const providerName = `cognito-idp.${config.region}.amazonaws.com/${config.userPoolId}`;
      credentialsRef.current = fromCognitoIdentityPool({
        client: new CognitoIdentityClient({ region: config.region }),
        identityPoolId: config.identityPoolId,
        logins: { [providerName]: session.idToken }
      });
    }
    return credentialsRef.current();
  }, [config.identityPoolId, config.region, config.userPoolId, session]);

  const value = useMemo(
    () => ({
      config,
      session,
      status,
      authError,
      login,
      register,
      confirmRegistration,
      logout,
      getCredentials
    }),
    [
      authError,
      config,
      confirmRegistration,
      getCredentials,
      login,
      logout,
      register,
      session,
      status
    ]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth requiere AuthProvider");
  return context;
}
