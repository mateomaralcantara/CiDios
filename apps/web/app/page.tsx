"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

interface Topic { slug: string; title: string; summary: string; content_status: string; claims: number }

export default function Home() {
  const [topics, setTopics] = useState<Topic[]>([]);
  const [q, setQ] = useState("");
  const router = useRouter();
  useEffect(() => { api<Topic[]>("/v1/topics").then(setTopics).catch(() => setTopics([])); }, []);
  return (
    <div>
      <section className="py-10">
        <p className="ui accent text-sm font-semibold uppercase tracking-widest">Enciclopedia universal inteligente</p>
        <h1 className="mt-2 text-4xl font-bold leading-tight md:text-5xl">La evidencia antes que la conclusión.</h1>
        <p className="muted mt-4 max-w-3xl text-lg">
          Investiga las grandes preguntas sobre Dios, el universo, la vida y la conciencia. Cada afirmación muestra
          su categoría epistémica, sus fuentes verificables, las posturas en disputa y lo que todavía no sabemos.
        </p>
        <form className="ui mt-6 flex max-w-2xl gap-2" onSubmit={(e) => { e.preventDefault(); router.push(`/biblioteca?q=${encodeURIComponent(q)}`); }}>
          <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar en la biblioteca: p. ej. «Códice de Alepo»" aria-label="Buscar" />
          <button className="btn btn-primary" disabled={q.trim().length < 2}>Buscar</button>
        </form>
        <div className="mt-4"><Link href="/investigar" className="ui underline">o lanza una investigación con el HARNESS →</Link></div>
      </section>
      <h2 className="mb-3 text-2xl font-semibold">Áreas de estudio</h2>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {topics.map((t) => (
          <Link key={t.slug} href={`/areas/${t.slug}`} className="card block p-4 transition hover:-translate-y-0.5" data-testid="topic-card">
            <h3 className="font-semibold">{t.title}</h3>
            <p className="muted mt-1 text-sm">{t.summary}</p>
            <p className="ui mt-3 text-xs">
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
