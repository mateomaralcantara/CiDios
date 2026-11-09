"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Doc { id: string; title: string; doc_kind: string; authors: string[]; license_code: string; visibility: string; review_status: string; chunks: number }
interface Result { chunk_id: string; document_id: string; document_title: string; locator: string; content: string; score: number; text_rank: number; semantic_score: number }

export default function Biblioteca() {
  const { session } = useAuth();
  const [docs, setDocs] = useState<Doc[]>([]);
  const [q, setQ] = useState("");
  const [mode, setMode] = useState<"hybrid" | "text" | "semantic">("hybrid");
  const [results, setResults] = useState<Result[] | null>(null);
  const [upload, setUpload] = useState({ title: "", body: "", rights_statement: "" });
  const [msg, setMsg] = useState<string | null>(null);
  const token = session?.token;
  const load = () => api<Doc[]>("/v1/library/documents", { token }).then(setDocs).catch(() => null);
  const run = async (query: string, m = mode) => {
    if (query.trim().length < 2) return;
    const r = await api<{ results: Result[] }>(`/v1/library/search?q=${encodeURIComponent(query)}&mode=${m}`, { token });
    setResults(r.results);
  };
  useEffect(() => {
    load();
    const initial = new URLSearchParams(window.location.search).get("q");
    if (initial) { setQ(initial); run(initial); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  return (
    <div>
      <h1 className="text-3xl font-bold">Biblioteca documental</h1>
      <p className="muted mt-2">Búsqueda textual (español sin acentos), semántica (modelo léxico local) o híbrida (fusión por rango recíproco). Respeta permisos: los documentos privados solo los ve su autor.</p>
      <form className="ui mt-5 flex flex-wrap gap-2" onSubmit={(e) => { e.preventDefault(); run(q); }}>
        <input className="input max-w-xl" aria-label="Consulta" value={q} onChange={(e) => setQ(e.target.value)} placeholder="¿Qué quieres encontrar?" />
        <select className="input w-auto" aria-label="Modo" value={mode} onChange={(e) => { const m = e.target.value as typeof mode; setMode(m); run(q, m); }}>
          <option value="hybrid">Híbrida</option><option value="text">Textual</option><option value="semantic">Semántica</option>
        </select>
        <button className="btn btn-primary">Buscar</button>
      </form>
      {results && (
        <section className="mt-6 space-y-3" aria-live="polite">
          <h2 className="ui text-sm font-semibold">{results.length} resultados</h2>
          {results.map((r) => (
            <div key={r.chunk_id} className="card p-4" data-testid="search-result">
              <div className="ui text-xs"><Link className="accent font-semibold underline" href={`/biblioteca/${r.document_id}`}>{r.document_title}</Link> · {r.locator}
                <span className="muted"> · puntuación {r.score.toFixed(4)} (texto {r.text_rank.toFixed(3)}, semántica {r.semantic_score.toFixed(3)})</span></div>
              <p className="mt-2 text-sm">{r.content}</p>
            </div>
          ))}
        </section>
      )}
      <section className="mt-10">
        <h2 className="mb-3 text-2xl font-semibold">Documentos</h2>
        <div className="grid gap-3 md:grid-cols-2">{docs.map((d) => (
          <Link key={d.id} href={`/biblioteca/${d.id}`} className="card block p-4">
            <h3 className="font-semibold">{d.title}</h3>
            <p className="ui muted mt-1 text-xs">{d.authors.join(", ")} · {d.doc_kind} · licencia {d.license_code} · {d.visibility} · {d.review_status} · {d.chunks} fragmentos</p>
          </Link>))}</div>
      </section>
      {session && (
        <section className="mt-10">
          <h2 className="mb-3 text-2xl font-semibold">Aportar un documento</h2>
          <form className="ui card space-y-3 p-5" onSubmit={async (e) => {
            e.preventDefault(); setMsg(null);
            try { await api("/v1/library/documents", { token, body: upload }); setMsg("Documento privado añadido."); setUpload({ title: "", body: "", rights_statement: "" }); load(); }
            catch (err) { setMsg((err as Error).message); }
          }}>
            <p className="muted text-xs">Solo documentos que tengas derecho a usar. Se guardan como privados; para publicarlos se requiere revisión editorial. El contenido se analiza para detectar instrucciones inyectadas.</p>
            <input className="input" placeholder="Título" required minLength={3} value={upload.title} onChange={(e) => setUpload({ ...upload, title: e.target.value })} />
            <textarea className="input min-h-32" placeholder="Texto (usa «## Sección» para localizar citas)" required minLength={50} value={upload.body} onChange={(e) => setUpload({ ...upload, body: e.target.value })} />
            <input className="input" placeholder="Declaración de derechos (p. ej. «texto propio»)" required minLength={5} value={upload.rights_statement} onChange={(e) => setUpload({ ...upload, rights_statement: e.target.value })} />
            <button className="btn btn-primary">Añadir</button>
            {msg && <p role="status" className="text-sm">{msg}</p>}
          </form>
        </section>
      )}
    </div>
  );
}
