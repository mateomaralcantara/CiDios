"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useAuth } from "@/lib/auth";

// Traduce los mensajes de Supabase Auth y explica qué hacer
function explain(raw: string): string {
  const m = raw.toLowerCase();
  if (m.includes("invalid login credentials"))
    return "Correo o contraseña incorrectos, o la cuenta todavía no existe. Si es tu primera vez, usa «Crear cuenta».";
  if (m.includes("email not confirmed"))
    return "Tu cuenta existe pero falta confirmar el correo. Abre el enlace que te enviamos o pulsa «Reenviar confirmación».";
  if (m.includes("already registered")) return "Ya existe una cuenta con ese correo. Usa «Entrar».";
  if (m.includes("rate limit"))
    return "Supabase limita el número de correos por hora. Espera unos minutos o crea el usuario desde el panel de Supabase (Authentication → Users → Add user).";
  if (m.includes("not authorized") || m.includes("address not authorized"))
    return "El servicio de correo de Supabase solo envía a miembros del equipo del proyecto. Crea el usuario en Supabase (Authentication → Users → Add user → «Auto Confirm User») o configura un SMTP propio.";
  if (m.includes("signups not allowed") || m.includes("signup is disabled"))
    return "El registro está desactivado en Supabase (Authentication → Sign In / Providers → «Allow new users to sign up»).";
  if (m.includes("password") && (m.includes("least") || m.includes("short") || m.includes("weak")))
    return "La contraseña no cumple los requisitos de Supabase (usa al menos 8 caracteres, con letras y números).";
  return raw;
}

export default function Entrar() {
  const { signInDev, signInPassword, signUp, resendConfirmation, resetPassword, supabase, devAuth } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();

  const run = async (fn: () => Promise<void>) => {
    setMsg(null); setBusy(true);
    try { await fn(); } catch (e) { setMsg({ kind: "error", text: explain((e as Error).message) }); } finally { setBusy(false); }
  };

  const submit = () => run(async () => {
    if (mode === "login") {
      await signInPassword(email, password);
      router.push("/investigar");
      return;
    }
    const r = await signUp(email, password);
    if (r === "logged_in") { router.push("/investigar"); return; }
    if (r === "already_registered") { setMode("login"); setMsg({ kind: "error", text: "Ya existe una cuenta con ese correo. Usa «Entrar» (o «¿Olvidaste tu contraseña?»)." }); return; }
    setMsg({ kind: "ok", text: `Cuenta creada. Te enviamos un correo a ${email}: abre el enlace para confirmarla y después entra aquí. Revisa también spam.` });
    setMode("login");
  });

  return (
    <div className="mx-auto max-w-md">
      <h1 className="text-3xl font-bold">{mode === "login" ? "Entrar" : "Crear cuenta"}</h1>
      {supabase ? (
        <>
          <div className="ui mt-4 flex justify-center gap-2" role="tablist">
            <button role="tab" aria-selected={mode === "login"} className={`btn ${mode === "login" ? "btn-primary" : ""}`}
              onClick={() => { setMode("login"); setMsg(null); }} data-testid="tab-login">Ya tengo cuenta</button>
            <button role="tab" aria-selected={mode === "signup"} className={`btn ${mode === "signup" ? "btn-primary" : ""}`}
              onClick={() => { setMode("signup"); setMsg(null); }} data-testid="tab-signup">Soy nuevo</button>
          </div>
          <form className="ui card mt-4 space-y-3 p-5" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <label className="block text-sm">Correo
              <input className="input mt-1" type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value.trim())} />
            </label>
            <label className="block text-sm">Contraseña {mode === "signup" && <span className="muted">(mínimo 8 caracteres)</span>}
              <input className="input mt-1" type={show ? "text" : "password"} autoComplete={mode === "login" ? "current-password" : "new-password"}
                required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <label className="flex items-center justify-center gap-2 text-xs"><input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} /> Mostrar contraseña</label>
            <button className="btn btn-primary w-full justify-center" disabled={busy} data-testid="submit-auth">
              {busy ? "Un momento…" : mode === "login" ? "Entrar" : "Crear cuenta"}
            </button>
            {mode === "login" && (
              <div className="flex flex-wrap justify-center gap-3 text-xs">
                <button type="button" className="underline" disabled={!email || busy}
                  onClick={() => run(async () => { await resendConfirmation(email); setMsg({ kind: "ok", text: `Correo de confirmación reenviado a ${email}.` }); })}>
                  Reenviar confirmación</button>
                <button type="button" className="underline" disabled={!email || busy}
                  onClick={() => run(async () => { await resetPassword(email); setMsg({ kind: "ok", text: `Si existe una cuenta con ${email}, te enviamos un enlace para cambiar la contraseña.` }); })}>
                  ¿Olvidaste tu contraseña?</button>
              </div>
            )}
          </form>
        </>
      ) : (
        <p className="ui muted mt-4 text-sm">Supabase Auth no está configurado en este despliegue (NEXT_PUBLIC_SUPABASE_URL).</p>
      )}
      {msg && <p role={msg.kind === "error" ? "alert" : "status"} data-testid="auth-message"
        className={`ui mt-4 text-sm ${msg.kind === "error" ? "text-rose-700" : "text-emerald-700"}`}>{msg.text}</p>}
      {devAuth && (
        <div className="ui card mt-6 p-5">
          <p className="text-sm font-semibold">Modo desarrollo</p>
          <p className="muted text-xs">Tokens locales firmados por la API; deshabilitados en staging y producción.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="btn" data-testid="dev-owner" onClick={() => run(async () => { await signInDev("owner"); router.push("/investigar"); })}>Propietario</button>
            <button className="btn" data-testid="dev-user" onClick={() => run(async () => { await signInDev("user"); router.push("/investigar"); })}>Usuario</button>
            <button className="btn" onClick={() => run(async () => { await signInDev("user2"); router.push("/investigar"); })}>Usuario 2</button>
          </div>
        </div>
      )}
    </div>
  );
}
