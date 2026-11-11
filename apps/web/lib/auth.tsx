"use client";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "./api";

export interface Session { token: string; userId: string; email: string | null; role: string }

interface AuthCtx {
  session: Session | null; ready: boolean; supabase: SupabaseClient | null; devAuth: boolean;
  signInDev: (who: "owner" | "user" | "user2") => Promise<void>;
  signInPassword: (email: string, password: string) => Promise<void>;
  signUp: (email: string, password: string) => Promise<"logged_in" | "confirm_email" | "already_registered">;
  resendConfirmation: (email: string) => Promise<void>;
  resetPassword: (email: string) => Promise<void>;
  /** true al volver del enlace «¿Olvidaste tu contraseña?»: hay que pedir la contraseña nueva */
  recovery: boolean;
  updatePassword: (password: string) => Promise<void>;
  /** Error que Supabase devuelve en la URL del enlace del correo (p. ej. enlace caducado) */
  linkError: string | null;
  signOut: () => Promise<void>;
}

const Ctx = createContext<AuthCtx | null>(null);
const KEY = "cdd.dev-session";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
// Clave pública del proyecto: «publishable key» (sb_publishable_…) o la «anon key» clásica. NUNCA la secret/service_role.
const SUPABASE_ANON = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const DEV_AUTH = process.env.NEXT_PUBLIC_DEV_AUTH === "true";
// Se lee al cargar el módulo, antes de que supabase-js procese y borre los parámetros del enlace del correo
const INITIAL_URL = typeof window !== "undefined" ? `${window.location.search}&${window.location.hash.replace(/^#/, "")}` : "";
const URL_PARAMS = new URLSearchParams(INITIAL_URL.replace(/^\?/, ""));

export function AuthProvider({ children }: { children: ReactNode }) {
  const supabase = useMemo(() => (SUPABASE_URL && SUPABASE_ANON ? createClient(SUPABASE_URL, SUPABASE_ANON) : null), []);
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [recovery, setRecovery] = useState(URL_PARAMS.get("type") === "recovery");
  const linkError = URL_PARAMS.get("error_description");

  const fromToken = useCallback(async (token: string): Promise<Session | null> => {
    try {
      const me = await api<{ user_id: string | null; role: string; email: string | null }>("/v1/me", { token });
      return me.user_id ? { token, userId: me.user_id, email: me.email, role: me.role } : null;
    } catch { return null; }
  }, []);

  useEffect(() => {
    (async () => {
      if (supabase) {
        // Suscribirse ANTES de getSession: el evento PASSWORD_RECOVERY se emite al procesar el enlace del correo
        supabase.auth.onAuthStateChange((event, s) => {
          if (event === "PASSWORD_RECOVERY") setRecovery(true);
          setTimeout(async () => setSession(s ? await fromToken(s.access_token) : null), 0);
        });
        const { data } = await supabase.auth.getSession();
        if (data.session) setSession(await fromToken(data.session.access_token));
      } else if (DEV_AUTH) {
        const raw = localStorage.getItem(KEY);
        if (raw) setSession(await fromToken(raw));
      }
      setReady(true);
    })();
  }, [supabase, fromToken]);

  const value: AuthCtx = {
    session, ready, supabase, devAuth: DEV_AUTH, recovery, linkError,
    updatePassword: async (password) => {
      if (!supabase) throw new Error("Supabase no está configurado");
      const { error } = await supabase.auth.updateUser({ password });
      if (error) throw error;
      setRecovery(false);
    },
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
      const { data, error } = await supabase.auth.signUp({
        email, password, options: { emailRedirectTo: `${window.location.origin}/entrar` },
      });
      if (error) throw error;
      // Supabase no revela si el correo ya existe: devuelve un usuario sin identidades
      if (data.user && (data.user.identities?.length ?? 0) === 0) return "already_registered";
      if (data.session) { setSession(await fromToken(data.session.access_token)); return "logged_in"; }
      return "confirm_email";
    },
    resendConfirmation: async (email) => {
      if (!supabase) throw new Error("Supabase no está configurado");
      const { error } = await supabase.auth.resend({ type: "signup", email, options: { emailRedirectTo: `${window.location.origin}/entrar` } });
      if (error) throw error;
    },
    resetPassword: async (email) => {
      if (!supabase) throw new Error("Supabase no está configurado");
      const { error } = await supabase.auth.resetPasswordForEmail(email, { redirectTo: `${window.location.origin}/entrar` });
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
