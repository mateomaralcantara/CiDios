"use client";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { api, formatDate } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface DocView {
  document: { title: string; authors: string[]; institution: string | null; doc_kind: string; license_code: string; rights_statement: string;
    provenance: Record<string, string>; consulted_at: string | null; content_sha256: string; review_status: string; visibility: string; language: string };
  chunks: { id: string; ordinal: number; locator: string; content: string; injection_risk: boolean; injection_signals: string[] }[];
  references: { id: string; authors: string[]; title: string; container_title: string | null; publisher: string | null; year: number | null; identifiers: Record<string, string>; identifier_check: string }[];
  license: { name: string; allows_full_text: boolean };
}

export default function DocPage() {
  const { id } = useParams<{ id: string }>();
  const { session, ready } = useAuth();
  const [d, setD] = useState<DocView | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { if (ready) api<DocView>(`/v1/library/documents/${id}`, { token: session?.token }).then(setD).catch((e) => setErr(e.message)); }, [id, ready, session]);
  if (err) return <p role="alert">{err}</p>;
  if (!d) return <p className="ui muted">Cargando…</p>;
  const doc = d.document;
  return (
    <article>
      <h1 className="text-3xl font-bold">{doc.title}</h1>
      <dl className="ui card prose-left mt-4 grid gap-x-6 gap-y-1 p-4 text-sm md:grid-cols-2">
        <div><dt className="muted inline">Autoría: </dt><dd className="inline">{doc.authors.join(", ")}{doc.institution ? ` (${doc.institution})` : ""}</dd></div>
        <div><dt className="muted inline">Tipo: </dt><dd className="inline">{doc.doc_kind} · {doc.language}</dd></div>
        <div><dt className="muted inline">Licencia: </dt><dd className="inline">{d.license.name}</dd></div>
        <div><dt className="muted inline">Derechos: </dt><dd className="inline">{doc.rights_statement}</dd></div>
        <div><dt className="muted inline">Revisión: </dt><dd className="inline">{doc.review_status} · {doc.visibility}</dd></div>
        <div><dt className="muted inline">Consultado: </dt><dd className="inline">{formatDate(doc.consulted_at)}</dd></div>
        <div className="md:col-span-2"><dt className="muted inline">Procedencia: </dt><dd className="inline">{Object.entries(doc.provenance).map(([k, v]) => `${k}: ${v}`).join(" · ")}</dd></div>
        <div className="md:col-span-2 break-all"><dt className="muted inline">SHA-256: </dt><dd className="inline font-mono text-xs">{doc.content_sha256}</dd></div>
      </dl>
      {!d.license.allows_full_text && <p className="ui mt-3 text-sm">La licencia solo permite mostrar extractos.</p>}
      <div className="mt-6 space-y-5">
        {d.chunks.map((c) => (
          <section key={c.id} id={c.id}>
            <h2 className="text-xl font-semibold">{c.locator}</h2>
            {c.injection_risk && <p className="ui chip mt-1 bg-rose-100 text-rose-900">Riesgo de inyección detectado: {c.injection_signals.join(", ")} — excluido como evidencia</p>}
            <p className="prose-left mx-auto mt-2 max-w-3xl whitespace-pre-line">{c.content}</p>
          </section>
        ))}
      </div>
      {d.references.length > 0 && (
        <section className="mt-8"><h2 className="mb-2 text-xl font-semibold">Fuentes que resume esta nota</h2>
          <ul className="list-disc pl-6 text-sm">{d.references.map((r) => (
            <li key={r.id}>{r.authors.join(", ")}, <em>{r.title}</em>{r.container_title ? `, ${r.container_title}` : ""}{r.publisher ? `, ${r.publisher}` : ""}{r.year ? ` (${r.year})` : ""}
              {r.identifiers?.url && <> · <a className="underline" href={r.identifiers.url} target="_blank" rel="noopener noreferrer">{r.identifiers.url}</a></>}
              <span className="ui muted text-xs"> · identificador: {r.identifier_check}</span></li>))}</ul></section>
      )}
    </article>
  );
}
