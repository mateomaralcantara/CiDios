"use client";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";

export interface Session { token: string; userId: string; email: string | null; role: string }

interface AuthCtx {
  session: Session | null; ready: boolean; supabase: SupabaseClient | null; devAuth: boolean;
  signInDev: (who: "owner" | "user" | "user2") => Promise<void>;
  signInPassword: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);
const KEY = "cdd.dev-session";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY; // clave pública (anon); nunca la service_role
const DEV_AUTH = process.env.NEXT_PUBLIC_DEV_AUTH === "true";

export function AuthProvider({ children }: { children: ReactNode }) {
  const supabase = useMemo(() => (SUPABASE_URL && SUPABASE_ANON ? createClient(SUPABASE_URL, SUPABASE_ANON) : null), []);
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);

  const fromToken = useCallback(async (token: string): Promise<Session | null> => {
    try {
      const me = await api<{ user_id: string | null; role: string; email: string | null }>("/v1/me", { token });
      return me.user_id ? { token, userId: me.user_id, email: me.email, role: me.role } : null;
    } catch { return null; }
  }, []);

  useEffect(() => {
    (async () => {
      if (supabase) {
        const { data } = await supabase.auth.getSession();
        if (data.session) setSession(await fromToken(data.session.access_token));
        supabase.auth.onAuthStateChange(async (_e, s) => setSession(s ? await fromToken(s.access_token) : null));
      } else if (DEV_AUTH) {
        const raw = localStorage.getItem(KEY);
        if (raw) setSession(await fromToken(raw));
      }
      setReady(true);
    })();
  }, [supabase, fromToken]);

  const value: AuthCtx = {
    session, ready, supabase, devAuth: DEV_AUTH,
    signInDev: async (who) => {
      const r = await api<{ access_token: string }>("/v1/auth/dev-token", { body: { user: who } });
      localStorage.setItem(KEY, r.access_token);
      setSession(await fromToken(r.access_token));
    },
    signInPassword: async (email, password) => {
      if (!supabase) throw new Error("Supabase no está configurado");
      const { error } = await supabase.auth.signInWithPassword({ email, password });
      if (error) throw error;
    },
    signUp: async (email, password) => {
      if (!supabase) throw new Error("Supabase no está configurado");
      const { error } = await supabase.auth.signUp({ email, password });
      if (error) throw error;
    },
    signOut: async () => {
      localStorage.removeItem(KEY);
      if (supabase) await supabase.auth.signOut();
      setSession(null);
    },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthCtx {
  const c = useContext(Ctx);
  if (!c) throw new Error("useAuth fuera de AuthProvider");
  return c;
}
