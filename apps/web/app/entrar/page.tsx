"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth";

export default function Entrar() {
  const { signInDev, signInPassword, signUp, supabase, devAuth } = useAuth();
  const [email, setEmail] = useState(""); const [password, setPassword] = useState("");
  const [msg, setMsg] = useState<string | null>(null);
  const router = useRouter();
  const go = async (fn: () => Promise<void>) => {
    setMsg(null);
    try { await fn(); router.push("/investigar"); } catch (e) { setMsg((e as Error).message); }
  };
  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-3xl font-bold">Entrar</h1>
      {supabase ? (
        <form className="ui card mt-6 space-y-3 p-5" onSubmit={(e) => { e.preventDefault(); go(() => signInPassword(email, password)); }}>
          <label className="block text-sm">Correo<input className="input mt-1" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} /></label>
          <label className="block text-sm">Contraseña<input className="input mt-1" type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} /></label>
          <div className="flex gap-2">
            <button className="btn btn-primary">Entrar</button>
            <button type="button" className="btn" onClick={() => go(async () => { await signUp(email, password); setMsg("Revisa tu correo para confirmar la cuenta."); })}>Crear cuenta</button>
          </div>
        </form>
      ) : (
        <p className="ui muted mt-4 text-sm">Supabase Auth no está configurado en este despliegue (NEXT_PUBLIC_SUPABASE_URL).</p>
      )}
      {devAuth && (
        <div className="ui card mt-6 p-5">
          <p className="text-sm font-semibold">Modo desarrollo</p>
          <p className="muted text-xs">Tokens locales firmados por la API; deshabilitados en staging y producción.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="btn" data-testid="dev-owner" onClick={() => go(() => signInDev("owner"))}>Propietario</button>
            <button className="btn" data-testid="dev-user" onClick={() => go(() => signInDev("user"))}>Usuario</button>
            <button className="btn" onClick={() => go(() => signInDev("user2"))}>Usuario 2</button>
          </div>
        </div>
      )}
      {msg && <p role="alert" className="ui mt-4 text-sm text-rose-700">{msg}</p>}
    </div>
  );
}
