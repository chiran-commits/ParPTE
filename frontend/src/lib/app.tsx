import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, token } from "./api";
import type { Meta, TaskMeta, User } from "./types";

interface AppState {
  user: User | null;
  meta: Meta | null;
  ready: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string) => Promise<void>;
  logout: () => void;
  setUser: (u: User) => void;
  task: (id: string) => TaskMeta | undefined;
}

const Ctx = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    api.get<Meta>("/api/meta").then(setMeta).catch(() => setMeta(null));
    if (!token.get()) {
      setReady(true);
      return;
    }
    api
      .get<User>("/api/auth/me")
      .then(setUser)
      .catch(() => token.set(null))
      .finally(() => setReady(true));
  }, []);

  useEffect(() => {
    const out = () => setUser(null);
    window.addEventListener("parpte:logout", out);
    return () => window.removeEventListener("parpte:logout", out);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const r = await api.post<{ token: string; user: User }>("/api/auth/login", { email, password });
    token.set(r.token);
    setUser(r.user);
  }, []);

  const register = useCallback(async (email: string, password: string, name: string) => {
    const r = await api.post<{ token: string; user: User }>("/api/auth/register", { email, password, name });
    token.set(r.token);
    setUser(r.user);
  }, []);

  const logout = useCallback(() => {
    token.set(null);
    setUser(null);
  }, []);

  const task = useCallback((id: string) => meta?.tasks.find((t) => t.id === id), [meta]);

  return <Ctx.Provider value={{ user, meta, ready, login, register, logout, setUser, task }}>{children}</Ctx.Provider>;
}

export function useApp() {
  const c = useContext(Ctx);
  if (!c) throw new Error("useApp outside provider");
  return c;
}

export const MODULE_LABEL: Record<string, string> = {
  speaking: "Speaking",
  writing: "Writing",
  reading: "Reading",
  listening: "Listening",
};
