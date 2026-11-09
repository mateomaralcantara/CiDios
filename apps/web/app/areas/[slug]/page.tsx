"use client";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { ClaimCard, CategoryChip } from "@/components/ClaimCard";
import { api } from "@/lib/api";
import type { ClaimRow, Perspective } from "@/lib/types";

interface Article {
  topic: { slug: string; title: string; summary: string; content_status: string; open_questions: string[] };
  claims: ClaimRow[];
  bibliography: { id: string; slug: string; authors: string[]; title: string; container_title: string | null; publisher: string | null; year: number | null; edition: string | null; identifiers: Record<string, string> }[];
}
interface Compare { rows: { claim_id: string; statement: string; category: string; category_label: string; balance: Record<string, number>; perspectives: Perspective[]; consensus_note: string }[]; note: string }

const GROUPS: [string, string[]][] = [
  ["Lo que documentan las fuentes", ["empirical_fact", "historical_document", "scholarly_consensus"]],
  ["Lo que se debate", ["contested", "scientific_hypothesis", "uncorroborated"]],
  ["Interpretaciones y argumentos", ["philosophical_argument", "theological_interpretation", "religious_belief"]],
  ["Preguntas abiertas", ["open_question"]],
];

export default function AreaPage() {
  const { slug } = useParams<{ slug: string }>();
  const [a, setA] = useState<Article | null>(null);
  const [cmp, setCmp] = useState<Compare | null>(null);
  const [view, setView] = useState<"article" | "compare">("article");
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    api<Article>(`/v1/topics/${slug}`).then(setA).catch((e) => setErr(e.message));
    api<Compare>(`/v1/topics/${slug}/compare`).then(setCmp).catch(() => null);
  }, [slug]);
  const grouped = useMemo(() => GROUPS.map(([h, cats]) => [h, (a?.claims ?? []).filter((c) => cats.includes(c.category))] as const), [a]);
  if (err) return <p role="alert">{err}</p>;
  if (!a) return <p className="ui muted">Cargando…</p>;
  return (
    <article>
      <p className="ui accent text-sm font-semibold">Artículo enciclopédico</p>
      <h1 className="text-4xl font-bold">{a.topic.title}</h1>
      <p className="muted mt-3 max-w-3xl text-lg">{a.topic.summary}</p>
      {a.claims.length === 0 ? (
        <p className="card ui mt-8 p-6">Esta área todavía no tiene afirmaciones verificadas. No se muestra contenido generado sin fuentes.</p>
      ) : (
        <>
          <div className="ui mt-6 flex gap-2" role="tablist">
            <button role="tab" aria-selected={view === "article"} className={`btn ${view === "article" ? "btn-primary" : ""}`} onClick={() => setView("article")}>Artículo</button>
            <button role="tab" aria-selected={view === "compare"} className={`btn ${view === "compare" ? "btn-primary" : ""}`} onClick={() => setView("compare")}>Comparador de perspectivas</button>
          </div>
          <p className="ui muted mt-3 text-xs">Contenido semilla redactado por el equipo editorial, pendiente de revisión por especialistas. Cada cita se comprueba literalmente contra su fuente.</p>
          {view === "article" ? (
            <div className="mt-6 space-y-10">
              {grouped.filter(([, cs]) => cs.length).map(([h, cs]) => (
                <section key={h}><h2 className="mb-3 text-2xl font-semibold">{h}</h2>
                  <div className="space-y-3">{cs.map((c) => <ClaimCard key={c.id} c={c} />)}</div></section>
              ))}
              {a.topic.open_questions.length > 0 && (
                <section><h2 className="mb-3 text-2xl font-semibold">Preguntas para investigar</h2>
                  <ul className="list-disc pl-6">{a.topic.open_questions.map((q) => <li key={q}>{q}</li>)}</ul></section>
              )}
              <section><h2 className="mb-3 text-2xl font-semibold">Bibliografía citada</h2>
                <ol className="space-y-1 text-sm">{a.bibliography.map((r) => (
                  <li key={r.id}>{r.authors.join(", ")}. <em>{r.title}</em>{r.container_title ? `. ${r.container_title}` : ""}{r.edition ? `. ${r.edition}` : ""}{r.publisher ? `. ${r.publisher}` : ""}{r.year ? `, ${r.year}` : ""}.
                    {r.identifiers?.url && <> <a className="underline" href={r.identifiers.url} rel="noopener noreferrer" target="_blank">{r.identifiers.url}</a></>}</li>
                ))}</ol>
                <p className="ui muted mt-2 text-xs">Los identificadores externos no se han resuelto en línea desde el servidor; verifíquelos antes de citarlos.</p>
              </section>
            </div>
          ) : (
            <div className="mt-6 overflow-x-auto">
              <p className="ui muted mb-3 text-sm">{cmp?.note}</p>
              <table className="ui w-full border-collapse text-sm">
                <thead><tr className="text-left"><th className="p-2">Afirmación</th><th className="p-2">Categoría</th><th className="p-2">Evidencia (a favor / en contra / matiza)</th><th className="p-2">Perspectivas</th></tr></thead>
                <tbody>{cmp?.rows.map((r) => (
                  <tr key={r.claim_id} className="border-t align-top" style={{ borderColor: "var(--line)" }}>
                    <td className="p-2" style={{ fontFamily: "ui-serif, Georgia, serif" }}>{r.statement}</td>
                    <td className="p-2"><CategoryChip category={r.category} label={r.category_label} /></td>
                    <td className="p-2 whitespace-nowrap">{r.balance.supports ?? 0} / {r.balance.challenges ?? 0} / {(r.balance.qualifies ?? 0) + (r.balance.contextualizes ?? 0)}</td>
                    <td className="p-2">{r.perspectives.map((p) => <div key={p.label} className="mb-1"><strong>{p.label}</strong> <span className="muted">({p.tradition})</span>: {p.summary}</div>)}</td>
                  </tr>))}</tbody>
              </table>
            </div>
          )}
        </>
      )}
    </article>
  );
}
