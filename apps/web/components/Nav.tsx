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
  const links = session?.role === "owner" ? [...LINKS, { href: "/admin", label: "Centro de control" }] : LINKS;
  const isActive = (href: string) => (href === "/" ? path === "/" || path?.startsWith("/areas") : path?.startsWith(href));
  return (
    <header className="ui sticky top-0 z-30 border-b backdrop-blur-md"
      style={{ borderColor: "var(--line)", background: "color-mix(in srgb, var(--bg) 82%, transparent)" }}>
      <nav className="mx-auto flex max-w-6xl flex-col items-center gap-3 px-4 py-4 text-center" aria-label="Principal">
        <Link href="/" className="flex items-center gap-3 text-[1.9rem] font-bold tracking-[0.2em] sm:text-[2.2rem]"
          style={{ fontFamily: "var(--font-serif)" }}>
          <img src="/icon.svg" alt="" width={44} height={44} className="rounded-xl shadow-sm" /> CIENCIA Y DIOS
        </Link>
        <div className="flex flex-wrap items-center justify-center gap-2">
          {links.map((l) => {
            const on = isActive(l.href);
            return (
              <Link key={l.href} href={l.href} aria-current={on ? "page" : undefined}
                className={`rounded-full px-4 py-1.5 text-[1.02rem] font-semibold transition ${on
                  ? "shadow-sm" : "muted hover:bg-[var(--accent-soft)] hover:text-[var(--accent)]"}`}
                style={on ? { background: "var(--accent)", color: "var(--bg)" } : undefined}>
                {l.label}
              </Link>
            );
          })}
        </div>
        <div className="flex flex-wrap items-center justify-center gap-3 text-[0.95rem]">
          {session ? (
            <>
              <span className="muted" data-testid="session-email">
                {session.email ?? session.userId.slice(0, 8)}
                <span className="chip ml-2" style={{ background: "var(--accent-soft)", color: "var(--accent)" }}>{session.role}</span>
              </span>
              <button className="btn" onClick={signOut}>Salir</button>
            </>
          ) : (
            <Link className="btn btn-primary" href="/entrar">Entrar</Link>
          )}
        </div>
      </nav>
    </header>
  );
}
