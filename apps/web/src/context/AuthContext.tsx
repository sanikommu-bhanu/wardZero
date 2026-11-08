import React, { createContext, useContext, useEffect, useState, useCallback } from "react";
import { authApi, setToken, ApiError } from "../lib/api";

interface AuthUser { id: string; email: string; role: string }

interface AuthContextValue {
  user: AuthUser | null;
  loading: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<void>;
  signUp: (fullName: string, email: string, password: string, role: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const bootstrap = useCallback(async () => {
    const stored = localStorage.getItem("wz_token");
    if (!stored) { setLoading(false); return; }
    try {
      const me = await authApi.me();
      setUser(me);
    } catch {
      setToken(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { bootstrap(); }, [bootstrap]);

  const signIn = useCallback(async (email: string, password: string) => {
    setError(null);
    try {
      const res = await authApi.signIn({ email, password });
      setToken(res.access_token);
      const me = await authApi.me();
      setUser(me);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Sign in failed";
      setError(msg);
      throw e;
    }
  }, []);

  const signUp = useCallback(async (full_name: string, email: string, password: string, role: string) => {
    setError(null);
    try {
      const res = await authApi.signUp({ full_name, email, password, role });
      setToken(res.access_token);
      const me = await authApi.me();
      setUser(me);
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Sign up failed";
      setError(msg);
      throw e;
    }
  }, []);

  const signOut = useCallback(() => {
    setToken(null);
    setUser(null);
  }, []);

  return (
    <AuthContext.Provider value={{ user, loading, error, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
