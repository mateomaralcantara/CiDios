"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { CategoryChip } from "@/components/ClaimCard";
import { api, formatDate } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { STANCE_LABEL, type ClaimRow } from "@/lib/types";

type Item = ClaimRow & { origin?: string; generated_by?: { model?: string }; topic_title?: string | null; created_at?: string; run_id?: string | null };
const CATEGORIES: [string, string][] = [
  ["empirical_fact", "Hecho empírico comprobable"], ["historical_document", "Documento o testimonio histórico"],
  ["scholarly_consensus", "Consenso académico"], ["scientific_hypothesis", "Hipótesis científica"],
  ["philosophical_argument", "Argumento filosófico"], ["theological_interpretation", "Interpretación teológica"],
  ["religious_belief", "Creencia o doctrina religiosa"], ["contested", "Afirmación controvertida"],
  ["uncorroborated", "Afirmación sin corroboración"], ["open_question", "Cuestión abierta"],
];

function ReviewCard({ c, token, onDone }: { c: Item; token: string; onDone: (msg: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [statement, setStatement] = useState(c.statement);
  const [category, setCategory] = useState(c.category);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const send = async (action: "approve" | "reject" | "edit") => {
    setBusy(true); setErr(null);
    try {
      const body: Record<string, string> = { action, note };
      if (editing || action === "edit") { body.statement = statement; body.category = category; }
      await api(`/v1/review/claims/${c.id}`, { token, body });
      onDone({ approve: "Aprobada y publicada", reject: "Rechazada", edit: "Cambios guardados" }[action]);
    } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <article className="card p-6 text-left" data-testid="review-card">
      <div className="ui flex flex-wrap items-center gap-2 text-sm">
        <CategoryChip category={c.category} label={c.category_label} />
        {c.origin === "llm_extracted" && <span className="chip border border-dashed">propuesta por {c.generated_by?.model ?? "IA"}</span>}
        {c.topic_title && <span className="muted">{c.topic_title}</span>}
        <span className="muted">· {formatDate(c.created_at)}</span>
        {c.run_id && <Link className="underline" href={`/ejecuciones/${c.run_id}`}>ver ejecución</Link>}
      </div>
      {editing ? (
        <div className="mt-4 space-y-3">
          <textarea className="input min-h-28" value={statement} onChange={(e) => setStatement(e.target.value)} aria-label="Afirmación" />
          <select className="input" value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Categoría epistémica">
            {CATEGORIES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
        </div>
      ) : <p className="mt-3 text-xl leading-relaxed">{c.statement}</p>}
      <p className="ui muted mt-2 text-sm">Afirmado por: {c.asserted_by} · {c.discipline}</p>
      <h3 className="ui mt-5 text-base font-semibold">Citas ({c.evidence.length}) — compruébalas antes de aprobar</h3>
      <div className="mt-2 space-y-2">
        {c.evidence.map((e) => (
          <blockquote key={e.id} className="rounded-lg border-l-4 p-3" style={{ borderColor: e.stance === "challenges" ? "#e11d48" : "var(--accent)", background: "var(--bg-2)" }}>
            <span className="ui chip mr-2 bg-stone-100 dark:bg-stone-800">{STANCE_LABEL[e.stance]}</span>“{e.exact_fragment}”
            <div className="ui muted mt-1 text-sm"><Link className="underline" href={`/biblioteca/${e.document_id}`}>{e.document_title}</Link> · {e.locator}</div>
          </blockquote>
        ))}
      </div>
      <input className="input mt-4" placeholder="Nota de revisión (opcional): por qué apruebas, corriges o rechazas" value={note} onChange={(e) => setNote(e.target.value)} />
      <div className="ui mt-4 flex flex-wrap gap-2">
        <button className="btn btn-primary" disabled={busy} onClick={() => send("approve")} data-testid="approve">✓ Aprobar y publicar</button>
        {editing
          ? <button className="btn" disabled={busy} onClick={() => send("edit")}>Guardar corrección</button>
          : <button className="btn" disabled={busy} onClick={() => setEditing(true)}>✎ Corregir</button>}
        <button className="btn" disabled={busy} onClick={() => send("reject")} data-testid="reject">✗ Rechazar</button>
      </div>
      {err && <p role="alert" className="ui mt-3 text-sm text-rose-700">{err}</p>}
    </article>
  );
}

export default function Revision() {
  const { session, ready } = useAuth();
  const [status, setStatus] = useState<"pending_review" | "reviewed" | "rejected">("pending_review");
  const [data, setData] = useState<{ claims: Item[]; counts: Record<string, number> } | null>(null);
  const [flash, setFlash] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const token = session?.token;
  const load = useCallback(() => {
    if (!token) return;
    api<{ claims: Item[]; counts: Record<string, number> }>(`/v1/review/claims?status=${status}`, { token })
      .then(setData).catch((e) => setErr(e.message));
  }, [token, status]);
  useEffect(load, [load]);
  if (!ready) return null;
  if (!session || !["owner", "editor"].includes(session.role))
    return <p className="ui">La revisión editorial es solo para editores y propietario. <Link className="underline" href="/entrar">Entrar</Link></p>;
  const c = data?.counts ?? {};
  return (
    <div>
      <h1>Revisión editorial</h1>
      <p className="muted mx-auto mt-3 max-w-3xl text-lg">
        Las afirmaciones propuestas por la IA son privadas hasta que un editor las aprueba. Comprueba que cada cita respalda
        lo que se afirma y que la categoría epistémica es honesta.
      </p>
      <div className="ui mt-6 flex flex-wrap justify-center gap-2" role="tablist">
        {([["pending_review", "Pendientes"], ["reviewed", "Aprobadas"], ["rejected", "Rechazadas"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={status === k} className={`btn ${status === k ? "btn-primary" : ""}`}
            onClick={() => { setStatus(k); setFlash(null); }}>{l} ({c[k] ?? 0})</button>
        ))}
      </div>
      {flash && <p role="status" className="ui mx-auto mt-4 max-w-lg rounded-xl border border-emerald-300 bg-emerald-50 px-4 py-2 text-emerald-800">{flash}</p>}
      {err && <p role="alert" className="ui mt-4 text-rose-700">{err}</p>}
      <div className="mx-auto mt-6 max-w-4xl space-y-5">
        {data && data.claims.length === 0 && <p className="ui card p-6">No hay afirmaciones en esta lista.</p>}
        {data?.claims.map((cl) => (
          <ReviewCard key={cl.id} c={cl} token={token!} onDone={(m) => { setFlash(m); load(); }} />
        ))}
      </div>
    </div>
  );
}
