import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ApiError, forgetSession, getCurrentUser, login, logout, subscribeSessionCheck } from "../api";
import { AuthContext } from "./context";

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [status, setStatus] = useState("loading");
  const [error, setError] = useState(null);
  const sessionCheck = useRef(null);
  const changingSession = useRef(false);

  const refreshUser = useCallback(async (signal, background = false) => {
    if (!signal) {
      sessionCheck.current?.abort();
      const controller = new AbortController();
      sessionCheck.current = controller;
      signal = controller.signal;
    }
    if (!background) setStatus("loading");
    setError(null);
    try {
      const identity = await getCurrentUser(signal);
      if (signal?.aborted) return null;
      setUser(identity);
      setStatus("ready");
      return identity;
    } catch (requestError) {
      if (signal?.aborted) return null;
      if (requestError instanceof ApiError && [401, 403].includes(requestError.status)) {
        setUser(null);
        forgetSession();
        setStatus("ready");
        return null;
      }
      setUser(null);
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
        if (controller.signal.aborted) return;
        setUser(identity);
        setStatus("ready");
        setError(null);
      })
      .catch((requestError) => {
        if (controller.signal.aborted) return;
        if (requestError instanceof ApiError && [401, 403].includes(requestError.status)) {
          setUser(null);
          forgetSession();
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

  useEffect(() => {
    const check = () => {
      if (changingSession.current) return;
      sessionCheck.current?.abort();
      const controller = new AbortController();
      sessionCheck.current = controller;
      refreshUser(controller.signal, true).catch(() => {});
    };
    const unsubscribe = subscribeSessionCheck(check);
    window.addEventListener('focus', check);
    return () => { sessionCheck.current?.abort(); unsubscribe(); window.removeEventListener('focus', check); };
  }, [refreshUser]);

  const signIn = useCallback(async (username, password) => {
    changingSession.current = true;
    sessionCheck.current?.abort();
    sessionCheck.current = null;
    setError(null);
    try {
      const identity = await login(username, password);
      setUser(identity);
      setStatus("ready");
      return identity;
    } finally { changingSession.current = false; }
  }, []);

  const signOut = useCallback(async () => {
    changingSession.current = true;
    sessionCheck.current?.abort();
    sessionCheck.current = null;
    try {
      try { await logout(); }
      catch (failure) {
        if (![401, 403].includes(failure.status) || await refreshUser() !== null) throw failure;
      }
      setUser(null);
      setStatus("ready");
      setError(null);
    } finally { changingSession.current = false; }
  }, [refreshUser]);

  const value = useMemo(
    () => ({ user, status, error, signIn, signOut, refreshUser }),
    [user, status, error, signIn, signOut, refreshUser],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
