import { createContext, ReactNode, useContext } from "react";
import { QueryClient, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, User } from "./api";

interface AuthValue {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<User>;
  logout: () => Promise<void>;
  refresh: () => Promise<unknown>;
}

const AuthContext = createContext<AuthValue | null>(null);

// При смене пользователя сбрасываем кэш всех данных, кроме запроса «кто я».
// Нельзя использовать qc.clear(): он отрывает от кэша запрос ["me"], и интерфейс не видит вход.
function dropOtherQueries(qc: QueryClient) {
  qc.removeQueries({ predicate: (q) => q.queryKey[0] !== "me" });
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["me"],
    retry: false,
    staleTime: 60_000,
    queryFn: async () => {
      try {
        return await api<User>("/auth/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
  });

  const value: AuthValue = {
    user: q.data ?? null,
    loading: q.isLoading,
    login: async (email, password) => {
      const u = await api<User>("/auth/login", { body: { email, password } });
      dropOtherQueries(qc);
      qc.setQueryData(["me"], u);
      return u;
    },
    logout: async () => {
      await api("/auth/logout", { method: "POST" });
      dropOtherQueries(qc);
      qc.setQueryData(["me"], null);
    },
    refresh: () => qc.invalidateQueries({ queryKey: ["me"] }),
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth вне AuthProvider");
  return ctx;
}
