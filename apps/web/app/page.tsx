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
      <section className="py-8 text-center sm:py-14">
        <p className="ui accent text-sm font-semibold uppercase tracking-[0.25em]">Enciclopedia universal inteligente</p>
        <h1 className="mt-3 tracking-[0.08em]" style={{ fontSize: "clamp(2.6rem, 1.6rem + 4vw, 4.4rem)" }}>CIENCIA Y DIOS</h1>
        <p className="accent mt-3 text-2xl italic md:text-3xl">La evidencia antes que la conclusión.</p>
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
