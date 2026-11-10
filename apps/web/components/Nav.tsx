"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/Logo";
import { useAuth } from "@/lib/auth";

const LINKS = [
  { href: "/", label: "Enciclopedia" },
  { href: "/biblioteca", label: "Biblioteca" },
  { href: "/investigar", label: "Investigar" },
];

export function Nav() {
  const { session, signOut } = useAuth();
  const path = usePathname();
  // Marca grande arriba; se compacta suavemente al bajar para no ocupar media pantalla
  const [compact, setCompact] = useState(false);
  useEffect(() => {
    const onScroll = () => setCompact((c) => (c ? window.scrollY > 40 : window.scrollY > 140));
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  const staff = session?.role === "owner" || session?.role === "editor";
  const links = [...LINKS, ...(staff ? [{ href: "/revision", label: "Revisión" }] : []),
                 ...(session?.role === "owner" ? [{ href: "/admin", label: "Centro de control" }] : [])];
  const isActive = (href: string) => (href === "/" ? path === "/" || path?.startsWith("/areas") : path?.startsWith(href));
  return (
    <header className="ui sticky top-0 z-30 border-b backdrop-blur-md"
      style={{ borderColor: "var(--line)", background: "color-mix(in srgb, var(--bg) 82%, transparent)" }}>
      <nav className={`mx-auto flex max-w-6xl flex-col items-center px-4 text-center transition-all duration-300 ${compact ? "gap-1 py-2 md:flex-row md:justify-between" : "gap-2 pb-4 pt-5"}`}
        aria-label="Principal">
        <Link href="/" aria-label="CIENCIA Y DIOS — inicio" data-testid="brand"
          className={`flex flex-col items-center gap-1 sm:flex-row ${compact ? "sm:gap-2" : "sm:gap-3"}`}>
          <span className="transition-all duration-300" style={{ width: compact ? 48 : "clamp(84px, 9vw, 120px)" }}>
            <Logo size={512} className="h-auto w-full drop-shadow-md" />
          </span>
          <span className="font-bold leading-none transition-all duration-300"
            style={{ fontFamily: "var(--font-serif)", letterSpacing: "0.015em", color: "var(--fg)",
                     fontSize: compact ? "clamp(1.3rem, 1rem + 1.4vw, 2rem)" : "clamp(2.1rem, 1rem + 5.2vw, 4.6rem)" }}>
            CIENCIA <span style={{ color: "var(--accent)" }}>Y</span> DIOS
          </span>
        </Link>
        <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-2">
        <div className="flex flex-wrap items-center justify-center gap-x-1 gap-y-2">
          {links.map((l) => {
            const on = isActive(l.href);
            return (
              <Link key={l.href} href={l.href} aria-current={on ? "page" : undefined}
                className={`rounded-full px-3 py-1.5 text-[0.9rem] font-semibold transition sm:px-4 sm:text-[1.02rem] ${on
                  ? "shadow-sm" : "muted hover:bg-[var(--accent-soft)] hover:text-[var(--accent)]"}`}
                style={on ? { background: "var(--accent)", color: "var(--bg)" } : undefined}>
                {l.label}
              </Link>
            );
          })}
        </div>
        <span className="hidden h-6 w-px sm:inline-block" style={{ background: "var(--line)" }} aria-hidden="true" />
        <div className="flex flex-wrap items-center justify-center gap-2 text-[0.95rem]">
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
        </div>
      </nav>
    </header>
  );
}
