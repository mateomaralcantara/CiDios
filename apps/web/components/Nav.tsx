"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/lib/auth";

const LINKS = [
  { href: "/", label: "Enciclopedia" },
  { href: "/biblioteca", label: "Biblioteca" },
  { href: "/investigar", label: "Investigar" },
];

export function Nav() {
  const { session, signOut } = useAuth();
  const path = usePathname();
  return (
    <header className="ui border-b" style={{ borderColor: "var(--line)" }}>
      <nav className="mx-auto flex max-w-6xl flex-col items-center gap-2 px-4 py-4 text-center" aria-label="Principal">
        <Link href="/" className="flex items-center gap-2 text-2xl font-bold tracking-[0.18em]" style={{ fontFamily: "ui-serif, Georgia, serif" }}>
          <img src="/icon.svg" alt="" width={30} height={30} /> CIENCIA Y DIOS
        </Link>
        <div className="flex flex-wrap items-center justify-center gap-x-5 gap-y-2">
        {LINKS.map((l) => (
          <Link key={l.href} href={l.href} aria-current={path === l.href ? "page" : undefined}
            className={`text-sm ${path === l.href ? "accent font-semibold" : "muted hover:underline"}`}>{l.label}</Link>
        ))}
        {session?.role === "owner" && (
          <Link href="/admin" className={`text-sm ${path?.startsWith("/admin") ? "accent font-semibold" : "muted hover:underline"}`}>
            Centro de control
          </Link>
        )}
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3 text-sm">
          {session ? (
            <>
              <span className="muted" data-testid="session-email">{session.email ?? session.userId.slice(0, 8)} · {session.role}</span>
              <button className="btn" onClick={signOut}>Salir</button>
            </>
          ) : (
            <Link className="btn" href="/entrar">Entrar</Link>
          )}
        </div>
      </nav>
    </header>
  );
}
