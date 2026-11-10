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
  const links = session?.role === "owner" ? [...LINKS, { href: "/admin", label: "Centro de control" }] : LINKS;
  const isActive = (href: string) => (href === "/" ? path === "/" || path?.startsWith("/areas") : path?.startsWith(href));
  return (
    <header className="ui sticky top-0 z-30 border-b backdrop-blur-md"
      style={{ borderColor: "var(--line)", background: "color-mix(in srgb, var(--bg) 82%, transparent)" }}>
      <nav className={`mx-auto flex max-w-6xl flex-col items-center px-4 text-center transition-all duration-300 ${compact ? "gap-2 py-2 md:flex-row md:justify-between" : "gap-4 py-6"}`}
        aria-label="Principal">
        <Link href="/" aria-label="CIENCIA Y DIOS — inicio" data-testid="brand"
          className={`flex flex-col items-center gap-3 sm:flex-row sm:gap-5 ${compact ? "sm:gap-3" : ""}`}>
          <span className="transition-all duration-300" style={{ width: compact ? 48 : "clamp(84px, 9vw, 120px)" }}>
            <Logo size={512} className="h-auto w-full drop-shadow-md" />
          </span>
          <span className="font-bold leading-none transition-all duration-300"
            style={{ fontFamily: "var(--font-serif)", letterSpacing: "0.14em", color: "var(--fg)",
                     fontSize: compact ? "clamp(1.3rem, 1rem + 1.4vw, 2rem)" : "clamp(2.1rem, 1rem + 5.2vw, 4.6rem)" }}>
            CIENCIA <span style={{ color: "var(--accent)" }}>Y</span> DIOS
          </span>
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
