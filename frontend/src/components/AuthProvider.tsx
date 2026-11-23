"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { ApiError, auth, getConfig } from "@/lib/api";
import type { Me, PublicConfig } from "@/lib/types";

interface AuthState {
  config: PublicConfig | null;
  me: Me | null;
  loading: boolean;
  refresh: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthState>({
  config: null,
  me: null,
  loading: true,
  refresh: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      setMe(await auth.me());
    } catch (e) {
      // 401: oturum yok. Diğer hatalarda da oturumsuz kabul edilir.
      if (!(e instanceof ApiError)) console.error(e);
      setMe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await auth.logout();
    } finally {
      setMe(null);
    }
  }, []);

  useEffect(() => {
    void refresh();
    getConfig()
      .then(setConfig)
      .catch(() => setConfig(null));
  }, [refresh]);

  return <AuthContext.Provider value={{ config, me, loading, refresh, logout }}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
