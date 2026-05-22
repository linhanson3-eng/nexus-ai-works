import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from "react";
import { api, setAuthToken } from "./api";
import type { UserInfo } from "./types";

interface AuthState {
  user: UserInfo | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

const TOKEN_KEY = "nexus_token";
const USER_KEY = "nexus_user";

function loadPersistedAuth(): { token: string | null; user: UserInfo | null } {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    const userRaw = localStorage.getItem(USER_KEY);
    const user = userRaw ? JSON.parse(userRaw) : null;
    return { token, user };
  } catch {
    return { token: null, user: null };
  }
}

function persistAuth(token: string, user: UserInfo) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserInfo | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore session on mount
  useEffect(() => {
    const persisted = loadPersistedAuth();
    if (persisted.token && persisted.user) {
      setToken(persisted.token);
      setUser(persisted.user);
      setAuthToken(persisted.token);
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const result = await api.marketLogin(username, password);
    setToken(result.token);
    setUser(result.user);
    setAuthToken(result.token);
    persistAuth(result.token, result.user);
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    const result = await api.marketRegister(username, password);
    setToken(result.token);
    setUser(result.user);
    setAuthToken(result.token);
    persistAuth(result.token, result.user);
  }, []);

  const logout = useCallback(() => {
    setToken(null);
    setUser(null);
    setAuthToken(null);
    clearAuth();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
