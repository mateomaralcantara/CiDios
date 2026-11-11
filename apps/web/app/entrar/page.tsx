"use client";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";

// Traduce los mensajes de Supabase Auth y explica qué hacer
function explain(raw: string): string {
  const m = raw.toLowerCase();
  if (m.includes("invalid login credentials"))
    return "Correo o contraseña incorrectos, o la cuenta todavía no existe. Si es tu primera vez, usa la pestaña «Soy nuevo».";
  if (m.includes("email not confirmed"))
    return "Tu cuenta existe pero falta confirmar el correo. Abre el enlace que te enviamos o pulsa «Reenviar confirmación».";
  if (m.includes("already registered")) return "Ya existe una cuenta con ese correo. Usa «Entrar».";
  if (m.includes("rate limit"))
    return "Supabase limita el número de correos por hora. Espera unos minutos o crea el usuario desde el panel de Supabase (Authentication → Users → Add user).";
  if (m.includes("not authorized") || m.includes("address not authorized"))
    return "El servicio de correo de Supabase solo envía a miembros del equipo del proyecto. Crea el usuario en Supabase (Authentication → Users → Add user → «Auto Confirm User») o configura un SMTP propio.";
  if (m.includes("signups not allowed") || m.includes("signup is disabled"))
    return "El registro está desactivado en Supabase (Authentication → Sign In / Providers → «Allow new users to sign up»).";
  if (m.includes("expired") || m.includes("invalid") && m.includes("link"))
    return "El enlace del correo ha caducado o ya se usó. Pide otro con «¿Olvidaste tu contraseña?» o «Reenviar confirmación».";
  if (m.includes("same") && m.includes("password"))
    return "La contraseña nueva debe ser distinta de la anterior.";
  if (m.includes("error sending") || m.includes("smtp"))
    return "Supabase no pudo enviar el correo. Revisa Authentication → Emails (SMTP) o usa en tu PC: python -m cdd.cuenta tu@correo --contrasena";
  if (m.includes("password") && (m.includes("least") || m.includes("short") || m.includes("weak")))
    return "La contraseña no cumple los requisitos de Supabase (usa al menos 8 caracteres, con letras y números).";
  return raw;
}

export default function Entrar() {
  const { signInDev, signInPassword, signUp, resendConfirmation, resetPassword, supabase, devAuth, recovery, updatePassword, linkError } = useAuth();
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [msg, setMsg] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const router = useRouter();
  useEffect(() => { if (linkError) setMsg({ kind: "error", text: explain(linkError) }); }, [linkError]);

  // Los botones de correo necesitan el correo escrito arriba: si falta, se dice en vez de no hacer nada
  const withEmail = (fn: () => Promise<void>) => () => {
    if (!email.includes("@")) { setMsg({ kind: "error", text: "Escribe primero tu correo electrónico en el campo de arriba." }); return; }
    run(fn);
  };

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

  if (recovery) return (
    <div className="mx-auto max-w-lg">
      <h1>Nueva contraseña</h1>
      <p className="muted mt-2 text-lg">Escribe la contraseña que quieres usar a partir de ahora.</p>
      <form className="ui card mt-5 space-y-5 p-6 text-left sm:p-8" data-testid="recovery-form"
        onSubmit={(e) => { e.preventDefault(); run(async () => { await updatePassword(password); router.push("/investigar"); }); }}>
        <label className="block text-base">Contraseña nueva <span className="muted font-normal">(mínimo 8 caracteres)</span>
          <input className="input mt-2" type={show ? "text" : "password"} autoComplete="new-password" required minLength={8}
            value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        <label className="muted flex cursor-pointer items-center gap-2 text-sm"><input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} /> Mostrar contraseña</label>
        <button className="btn btn-primary w-full py-3 text-lg" disabled={busy}>{busy ? "Guardando…" : "Guardar y entrar"}</button>
        {msg && <p role="alert" className={`text-base ${msg.kind === "error" ? "text-rose-700" : "text-emerald-700"}`}>{msg.text}</p>}
      </form>
    </div>
  );

  return (
    <div className="mx-auto max-w-lg">
      <h1>{mode === "login" ? "Entrar" : "Crear cuenta"}</h1>
      <p className="muted mt-2 text-lg">
        {mode === "login" ? "Accede para investigar, guardar tu progreso y consultar tus fuentes."
          : "Crea tu cuenta gratuita. Te enviaremos un correo para confirmarla."}
      </p>
      {supabase ? (
        <>
          <div className="ui mx-auto mt-6 inline-flex rounded-full border p-1" role="tablist"
            style={{ borderColor: "var(--line)", background: "var(--bg-2)" }}>
            {(["login", "signup"] as const).map((m) => (
              <button key={m} role="tab" aria-selected={mode === m} data-testid={m === "login" ? "tab-login" : "tab-signup"}
                onClick={() => { setMode(m); setMsg(null); }}
                className="rounded-full px-5 py-2 text-base font-semibold transition"
                style={mode === m ? { background: "var(--card)", color: "var(--accent)", boxShadow: "var(--shadow)" } : { color: "var(--muted)" }}>
                {m === "login" ? "Ya tengo cuenta" : "Soy nuevo"}
              </button>
            ))}
          </div>
          <form className="ui card mt-5 space-y-5 p-6 text-left sm:p-8" onSubmit={(e) => { e.preventDefault(); submit(); }}>
            <label className="block text-base">Correo electrónico
              <input className="input mt-2" type="email" placeholder="tu@correo.com" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value.trim())} />
            </label>
            <label className="block text-base">Contraseña {mode === "signup" && <span className="muted font-normal">(mínimo 8 caracteres)</span>}
              <input className="input mt-2" type={show ? "text" : "password"} placeholder="••••••••" autoComplete={mode === "login" ? "current-password" : "new-password"}
                required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
            </label>
            <label className="muted flex cursor-pointer items-center gap-2 text-sm"><input type="checkbox" checked={show} onChange={(e) => setShow(e.target.checked)} /> Mostrar contraseña</label>
            <button className="btn btn-primary w-full py-3 text-lg" disabled={busy} data-testid="submit-auth">
              {busy ? "Un momento…" : mode === "login" ? "Entrar" : "Crear cuenta"}
            </button>
            {mode === "login" && (
              <div className="flex flex-wrap justify-center gap-x-5 gap-y-2 border-t pt-4 text-sm" style={{ borderColor: "var(--line)" }}>
                <button type="button" className="underline" disabled={busy} data-testid="resend"
                  onClick={withEmail(async () => { await resendConfirmation(email); setMsg({ kind: "ok", text: `Correo de confirmación reenviado a ${email}.` }); })}>
                  Reenviar confirmación</button>
                <button type="button" className="underline" disabled={busy} data-testid="forgot"
                  onClick={withEmail(async () => { await resetPassword(email); setMsg({ kind: "ok", text: `Si existe una cuenta con ${email}, te enviamos un enlace para cambiar la contraseña.` }); })}>
                  ¿Olvidaste tu contraseña?</button>
              </div>
            )}
          </form>
        </>
      ) : (
        <p className="ui muted mt-4 text-sm">Supabase Auth no está configurado en este despliegue (NEXT_PUBLIC_SUPABASE_URL).</p>
      )}
      {msg && <p role={msg.kind === "error" ? "alert" : "status"} data-testid="auth-message"
        className={`ui mx-auto mt-5 max-w-lg rounded-xl border px-4 py-3 text-base ${msg.kind === "error"
          ? "border-rose-300 bg-rose-50 text-rose-800 dark:border-rose-800 dark:bg-rose-950/40 dark:text-rose-200"
          : "border-emerald-300 bg-emerald-50 text-emerald-800 dark:border-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-200"}`}>{msg.text}</p>}
      {devAuth && (
        <div className="ui card mt-8 p-6">
          <p className="font-semibold">Modo desarrollo</p>
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
