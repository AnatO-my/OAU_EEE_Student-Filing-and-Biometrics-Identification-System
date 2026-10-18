import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, getCurrentUser, login, logout } from "../api";
import { AuthContext } from "./context";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const sessionCheck = useRef(null);

  const refreshUser = useCallback(async (signal) => {
    setStatus("loading");
    setError(null);
    try {
      const identity = await getCurrentUser(signal);
      setUser(identity);
      setStatus("ready");
      return identity;
    } catch (requestError) {
      if (signal?.aborted) return null;
      if (requestError instanceof ApiError && [401, 403].includes(requestError.status)) {
        setUser(null);
        setStatus("ready");
        return null;
      }
      setError(requestError);
      setStatus("error");
      throw requestError;
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    sessionCheck.current = controller;
    getCurrentUser(controller.signal)
      .then((identity) => {
        setUser(identity);
        setStatus("ready");
        setError(null);
      })
      .catch((requestError) => {
        if (controller.signal.aborted) return;
        if (requestError instanceof ApiError && [401, 403].includes(requestError.status)) {
          setUser(null);
          setStatus("ready");
          setError(null);
          return;
        }
        setError(requestError);
        setStatus("error");
      });
    return () => {
      controller.abort();
      if (sessionCheck.current === controller) sessionCheck.current = null;
    };
  }, []);

  const signIn = useCallback(async (username, password) => {
    sessionCheck.current?.abort();
    sessionCheck.current = null;
    setError(null);
    const identity = await login(username, password);
    setUser(identity);
    setStatus("ready");
    return identity;
  }, []);

  const signOut = useCallback(async () => {
    sessionCheck.current?.abort();
    sessionCheck.current = null;
    await logout();
    setUser(null);
    setStatus("ready");
    setError(null);
  }, []);

  const value = useMemo(
    () => ({ user, status, error, signIn, signOut, refreshUser }),
    [user, status, error, signIn, signOut, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
