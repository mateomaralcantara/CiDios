"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { API_URL, api, formatDate, formatUsd } from "@/lib/api";
import { useAuth } from "@/lib/auth";

interface Task { task_key: string; agent_code: string; phase: string; depends_on: string[]; status: string; attempts: number; cost_usd: string;
  allowed_tools: string[]; agent_version: string; completion_criteria: string; error: string | null; started_at: string | null; finished_at: string | null }
interface RunDetail {
  run: { id: string; state: string; previous_state: string | null; budget_usd: string; spent_usd: string; estimated_usd: string; requires_approval: boolean;
    approved_at: string | null; error: string | null; result: { experience_id?: string; claims?: number; excluded?: number; no_evidence?: boolean; message?: string; suggestions?: string[] }; created_at: string; owner_id: string };
  investigation: { prompt: string; intent: Record<string, unknown> };
  tasks: Task[]; costs: { kind: string; agent_code: string | null; provider: string; model: string; amount_usd: string; cache_hit: boolean; note: string; created_at: string }[];
  checkpoints: { task_key: string; state: string; output_sha256: string }[]; state_chain: string[];
}
interface Ev { id: number; task_key: string | null; level: string; event_type: string; message: string; created_at: string }

const STATUS_COLOR: Record<string, string> = { succeeded: "bg-emerald-500", running: "bg-amber-500 animate-pulse", failed: "bg-rose-600", queued: "bg-stone-300", blocked: "bg-rose-300" };
const ACTIVE = new Set(["READY", "PUBLISHED", "FAILED", "CANCELLED", "PARTIAL"]);

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const { session, ready } = useAuth();
  const [d, setD] = useState<RunDetail | null>(null);
  const [events, setEvents] = useState<Ev[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const token = session?.token;
  const seen = useRef(new Set<number>());

  const refresh = useCallback(() => {
    if (token) api<RunDetail>(`/v1/runs/${id}`, { token }).then(setD).catch((e) => setErr(e.message));
  }, [id, token]);

  useEffect(() => {
    if (!token) return;
    refresh();
    const es = new EventSource(`${API_URL}/v1/runs/${id}/stream?access_token=${encodeURIComponent(token)}`);
    es.addEventListener("harness", (m) => {
      const e = JSON.parse((m as MessageEvent).data) as Ev;
      if (seen.current.has(e.id)) return;
      seen.current.add(e.id);
      setEvents((prev) => [...prev, e]);
      if (e.event_type === "state_change" || e.event_type.startsWith("task_")) refresh();
    });
    es.addEventListener("state", (m) => { const s = JSON.parse((m as MessageEvent).data).state; if (ACTIVE.has(s)) { refresh(); } });
    es.onerror = () => es.close();
    return () => es.close();
  }, [id, token, refresh]);

  const act = async (path: string, body?: unknown) => {
    setErr(null);
    try { await api(`/v1/runs/${id}/${path}`, { token, method: "POST", body }); refresh(); } catch (e) { setErr((e as Error).message); }
  };

  if (ready && !session) return <p className="ui">Necesitas <Link className="underline" href="/entrar">entrar</Link>.</p>;
  if (!d) return <p className="ui muted">{err ?? "Cargando…"}</p>;
  const r = d.run;
  const chainIdx = d.state_chain.indexOf(r.state === "PAUSED" || r.state === "AWAITING_APPROVAL" || r.state === "BUDGET_EXHAUSTED" ? (r.previous_state ?? "") : r.state);
  const isOwner = session?.role === "owner";
  return (
    <div className="ui">
      <p className="accent text-sm font-semibold">Ejecución del HARNESS</p>
      <h1 className="text-2xl font-bold" style={{ fontFamily: "ui-serif, Georgia, serif" }}>{d.investigation.prompt.slice(0, 160)}{d.investigation.prompt.length > 160 ? "…" : ""}</h1>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        <span className="chip bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900 text-sm" data-testid="run-state">{r.state}</span>
        <span className="text-sm">Gasto {formatUsd(r.spent_usd)} / presupuesto {formatUsd(r.budget_usd)} · estimado {formatUsd(r.estimated_usd)}</span>
        {r.result?.experience_id && <Link data-testid="open-experience" className="btn btn-primary" href={`/experiencias/${r.result.experience_id}`}>Abrir experiencia →</Link>}
      </div>
      <ol className="mt-5 flex flex-wrap justify-center gap-1 text-[11px]" aria-label="Cadena de estados">
        {d.state_chain.map((s, i) => (
          <li key={s} className={`rounded px-2 py-1 ${i <= chainIdx ? "bg-emerald-600 text-white" : "bg-stone-200 dark:bg-stone-800"} ${s === r.state ? "ring-2 ring-amber-500" : ""}`}>{s}</li>
        ))}
      </ol>
      {r.error && <p role="alert" className="mt-3 text-sm text-rose-700">Error: {r.error}</p>}
      {r.result?.no_evidence && (
        <div className="card mx-auto mt-4 max-w-3xl p-4" role="status" data-testid="no-evidence">
          <p className="font-semibold">Sin evidencia suficiente</p>
          <p className="mt-1 text-sm">{r.result.message}</p>
          {r.result.suggestions && <ul className="list-disc mt-2 pl-5 text-sm">{r.result.suggestions.map((x) => <li key={x}>{x}</li>)}</ul>}
          <p className="muted mt-2 text-xs">Ciencia y Dios no genera contenido sin fuentes verificables.</p>
        </div>
      )}
      {r.state === "AWAITING_APPROVAL" && <p className="mt-3 text-sm">Esta investigación requiere aprobación explícita del propietario para el gasto estimado.</p>}
      <div className="mt-4 flex flex-wrap gap-2">
        {!ACTIVE.has(r.state) && !["PAUSED", "AWAITING_APPROVAL", "BUDGET_EXHAUSTED"].includes(r.state) && <button className="btn" onClick={() => act("pause")}>Pausar</button>}
        {["PAUSED", "BUDGET_EXHAUSTED"].includes(r.state) && <button className="btn" onClick={() => act("resume")}>Reanudar</button>}
        {!ACTIVE.has(r.state) && <button className="btn" onClick={() => act("cancel")}>Cancelar</button>}
        {isOwner && r.state === "AWAITING_APPROVAL" && <button className="btn btn-primary" onClick={() => act("approve")}>Aprobar gasto</button>}
        {isOwner && r.state === "BUDGET_EXHAUSTED" && <button className="btn" onClick={() => { const v = prompt("Nuevo presupuesto (USD)", r.budget_usd); if (v) act("budget", { budget_usd: v }); }}>Ajustar presupuesto</button>}
        {isOwner && r.state === "READY" && <button className="btn btn-primary" data-testid="publish" onClick={() => act("publish")}>Aprobar y publicar</button>}
      </div>
      {err && <p role="alert" className="mt-2 text-sm text-rose-700">{err}</p>}

      <h2 className="mt-8 text-lg font-semibold">Plan (DAG) y tareas</h2>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full text-sm">
          <thead><tr className="text-left muted"><th className="p-1">Tarea</th><th className="p-1">Agente</th><th className="p-1">Fase</th><th className="p-1">Depende de</th><th className="p-1">Estado</th><th className="p-1">Intentos</th><th className="p-1">Coste</th><th className="p-1">Criterio de terminación</th></tr></thead>
          <tbody>{d.tasks.map((t) => (
            <tr key={t.task_key} className="border-t" style={{ borderColor: "var(--line)" }} data-testid={`task-${t.task_key}`}>
              <td className="p-1 font-mono text-xs">{t.task_key}</td><td className="p-1">{t.agent_code} <span className="muted">v{t.agent_version}</span></td>
              <td className="p-1">{t.phase}</td><td className="p-1 text-xs">{t.depends_on.join(", ") || "—"}</td>
              <td className="p-1"><span className={`mr-1 inline-block h-2 w-2 rounded-full ${STATUS_COLOR[t.status] ?? "bg-stone-400"}`} />{t.status}{t.error ? ` — ${t.error}` : ""}</td>
              <td className="p-1">{t.attempts}</td><td className="p-1">{formatUsd(t.cost_usd)}</td><td className="p-1 text-xs muted">{t.completion_criteria}</td>
            </tr>))}</tbody>
        </table>
      </div>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <section>
          <div className="flex items-center justify-between"><h2 className="text-lg font-semibold">Traza en vivo (SSE)</h2>
            <label className="text-xs"><input type="checkbox" checked={showDebug} onChange={(e) => setShowDebug(e.target.checked)} /> llamadas a herramientas</label></div>
          <ol className="card prose-left mt-2 max-h-96 space-y-1 overflow-y-auto p-3 font-mono text-[11px]" aria-live="polite">
            {events.filter((e) => showDebug || e.level !== "debug").map((e) => (
              <li key={e.id} className={e.level === "error" ? "text-rose-600" : e.level === "warning" ? "text-amber-600" : e.level === "audit" ? "accent" : ""}>
                {new Date(e.created_at).toLocaleTimeString("es")} [{e.level}] {e.task_key ? `${e.task_key}: ` : ""}{e.message}
              </li>))}
          </ol>
        </section>
        <section>
          <h2 className="text-lg font-semibold">Costes registrados</h2>
          <table className="card mt-2 w-full text-xs"><tbody>{d.costs.map((c, i) => (
            <tr key={i} className="border-t" style={{ borderColor: "var(--line)" }}><td className="p-1">{c.kind}</td><td className="p-1">{c.agent_code ?? "plan"}</td>
              <td className="p-1">{c.provider}/{c.model}</td><td className="p-1">{formatUsd(c.amount_usd)}</td><td className="p-1 muted">{c.cache_hit ? "caché · " : ""}{c.note}</td></tr>))}</tbody></table>
          <h2 className="mt-6 text-lg font-semibold">Checkpoints</h2>
          <ul className="mt-2 text-xs">{d.checkpoints.map((c) => <li key={c.task_key} className="font-mono">{c.task_key} · {c.state} · {c.output_sha256.slice(0, 16)}…</li>)}</ul>
          <p className="muted mt-4 text-xs">Creada {formatDate(r.created_at)}</p>
        </section>
      </div>
    </div>
  );
}
