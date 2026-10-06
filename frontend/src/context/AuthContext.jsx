import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { api, clearToken, getToken, setToken } from '../services/apiClient.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore the session on load: a stored token is only trusted once the
  // server has confirmed it, so an expired token logs the user out cleanly.
  useEffect(() => {
    if (!getToken()) {
      setIsLoading(false);
      return;
    }
    api
      .me()
      .then(setUser)
      .catch(() => {
        clearToken();
        setUser(null);
      })
      .finally(() => setIsLoading(false));
  }, []);

  const login = useCallback(async (email, password) => {
    const { access_token: accessToken } = await api.login({ email, password });
    setToken(accessToken);
    setUser(await api.me());
  }, []);

  const register = useCallback(async (email, fullName, password) => {
    await api.register({ email, full_name: fullName, password });
    const { access_token: accessToken } = await api.login({ email, password });
    setToken(accessToken);
    setUser(await api.me());
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const value = useMemo(
    () => ({ user, isLoading, login, register, logout }),
    [user, isLoading, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider.');
  return context;
}
