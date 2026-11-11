"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Topic { slug: string; title: string; summary: string; content_status: string; claims: number }

export default function Home() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [q, setQ] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const router = useRouter();
  useEffect(() => { api<Topic[]>("/v1/topics").then(setTopics).catch((e) => { setTopics([]); setErr((e as Error).message); }); }, []);
  return (
    <div>
      <section className="pb-8 pt-2 text-center sm:pb-12 sm:pt-4">
        <p className="ui accent text-sm font-semibold uppercase tracking-[0.12em]">Enciclopedia universal inteligente</p>
        <h1 className="accent mt-2 italic" style={{ fontSize: "clamp(2rem, 1.2rem + 3vw, 3.4rem)" }}>
          La evidencia antes que la conclusión.
        </h1>
        <p className="muted mx-auto mt-5 max-w-3xl text-xl leading-relaxed">
          Investiga las grandes preguntas sobre Dios, el universo, la vida y la conciencia. Cada afirmación muestra
          su categoría epistémica, sus fuentes verificables, las posturas en disputa y lo que todavía no sabemos.
        </p>
        <form className="ui mx-auto mt-8 flex max-w-2xl flex-col gap-3 sm:flex-row" onSubmit={(e) => { e.preventDefault(); router.push(`/biblioteca?q=${encodeURIComponent(q)}`); }}>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar en la biblioteca: p. ej. «Códice de Alepo»" aria-label="Buscar" />
          <button className="btn btn-primary px-7" disabled={q.trim().length < 2}>Buscar</button>
        </form>
        <div className="mt-5"><Link href="/investigar" className="ui accent text-lg font-semibold underline">o lanza una investigación con el HARNESS →</Link></div>
      </section>
      <h2 className="mb-6 text-center">Áreas de estudio</h2>
      {err && <p role="alert" className="ui card mx-auto mb-6 max-w-3xl p-4 text-center text-base text-rose-700" data-testid="api-error">{err}</p>}
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {topics.map((t) => (
          <Link key={t.slug} href={`/areas/${t.slug}`} className="card block p-6 text-center" data-testid="topic-card">
            <h3>{t.title}</h3>
            <p className="muted mt-2 text-base leading-relaxed">{t.summary}</p>
            <p className="ui mt-4 text-sm">
              {t.content_status === "empty"
                ? <span className="muted">Sin contenido verificado todavía</span>
                : <span className="accent font-semibold">{t.claims} afirmaciones con evidencia · semilla pendiente de revisión</span>}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
