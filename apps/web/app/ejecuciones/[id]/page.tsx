"use client";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Chronosphere } from "@/components/Chronosphere";
import { API_URL, api, formatDate, formatUsd } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Experience } from "@/lib/types";

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
const TERMINAL = new Set(["READY", "PUBLISHED", "FAILED", "CANCELLED", "PARTIAL"]);

// Lo que ve una persona: pasos con sentido, no estados internos
const STEPS = [
  { icon: "✦", label: "Comprender la pregunta", states: ["CREATED", "AUTHORIZED", "PLANNED"] },
  { icon: "⌕", label: "Buscar fuentes", states: ["ACQUIRING"] },
  { icon: "❝", label: "Leer y extraer hechos", states: ["ANALYZING"] },
  { icon: "⚖", label: "Contrastar posturas", states: ["CROSS_EXAMINING"] },
  { icon: "✓", label: "Verificar cada cita", states: ["VERIFYING"] },
  { icon: "◷", label: "Componer la línea de tiempo", states: ["PACKAGING", "RENDERING", "QA"] },
];
const HUMAN_STATE: Record<string, string> = {
  READY: "Lista · pendiente de publicar", PUBLISHED: "Publicada", FAILED: "No se pudo completar", CANCELLED: "Cancelada",
  PARTIAL: "Sin evidencia suficiente", PAUSED: "En pausa", AWAITING_APPROVAL: "Esperando aprobación", BUDGET_EXHAUSTED: "Detenida por presupuesto",
};
const TECHNICAL = /usd|coste|presupuesto|token|modelo|model|gemini|checkpoint|sha256|llm|reserva|intento/i;

export default function RunPage() {
  const { id } = useParams<{ id: string }>();
  const { session, ready } = useAuth();
  const [d, setD] = useState<RunDetail | null>(null);
  const [exp, setExp] = useState<Experience | null>(null);
  const [events, setEvents] = useState<Ev[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const token = session?.token;
  const seen = useRef(new Set<number>());

  const load = useCallback(() => {
    if (token) api<RunDetail>(`/v1/runs/${id}`, { token }).then(setD).catch((e) => setErr(e.message));
  }, [id, token]);
  // Agrupa las recargas: como máximo una por segundo aunque lleguen muchos eventos seguidos
  const pending = useRef<ReturnType<typeof setTimeout> | null>(null);
  const refresh = useCallback(() => {
    if (pending.current) return;
    pending.current = setTimeout(() => { pending.current = null; load(); }, 1000);
  }, [load]);

  useEffect(() => {
    if (!token) return;
    load();
    const es = new EventSource(`${API_URL}/v1/runs/${id}/stream?access_token=${encodeURIComponent(token)}`);
    es.addEventListener("harness", (m) => {
      const e = JSON.parse((m as MessageEvent).data) as Ev;
      if (seen.current.has(e.id)) return;
      seen.current.add(e.id);
      setEvents((prev) => [...prev, e]);
      if (e.event_type === "state_change" || e.event_type.startsWith("task_")) refresh();
    });
    es.addEventListener("state", (m) => { const s = JSON.parse((m as MessageEvent).data).state; if (TERMINAL.has(s)) refresh(); });
    es.onerror = () => es.close();
    return () => es.close();
  }, [id, token, refresh]);

  const expId = d?.run.result?.experience_id;
  useEffect(() => {
    if (expId && token) api<Experience>(`/v1/experiences/${expId}`, { token }).then(setExp).catch(() => null);
  }, [expId, token, d?.run.state]);

  const titles = useMemo(() => new Map((exp?.experience_spec.events ?? []).map((e) => [e.claim_id, e.title])), [exp]);

  const act = async (path: string, body?: unknown) => {
    setErr(null);
    try { await api(`/v1/runs/${id}/${path}`, { token, method: "POST", body }); refresh(); } catch (e) { setErr((e as Error).message); }
  };

  if (ready && !session) return <p className="ui">Necesitas <Link className="underline" href="/entrar">entrar</Link>.</p>;
  if (!d) return <p className="ui muted">{err ?? "Cargando…"}</p>;
  const r = d.run;
  const isOwner = session?.role === "owner";
  const effective = ["PAUSED", "AWAITING_APPROVAL", "BUDGET_EXHAUSTED"].includes(r.state) ? (r.previous_state ?? "CREATED") : r.state;
  const finished = r.state === "READY" || r.state === "PUBLISHED";
  const stepIdx = finished ? STEPS.length : Math.max(0, STEPS.findIndex((s) => s.states.includes(effective)));
  const running = !TERMINAL.has(r.state);
  const feed = events.filter((e) => e.level !== "debug" && !TECHNICAL.test(e.message)).slice(-6).reverse();

  return (
    <div className="ui">
      <p className="accent text-sm font-semibold uppercase tracking-[0.14em]">Investigación</p>
      <h1 className="mx-auto mt-2 max-w-4xl text-3xl font-bold" style={{ fontFamily: "var(--font-serif)" }}>
        {d.investigation.prompt.slice(0, 180)}{d.investigation.prompt.length > 180 ? "…" : ""}</h1>
      <div className="mt-4 flex flex-wrap items-center justify-center gap-3">
        <span className="chip bg-stone-900 px-4 py-1 text-sm text-white dark:bg-stone-100 dark:text-stone-900">
          {HUMAN_STATE[r.state] ?? "Investigando…"} <span className="ml-1 font-mono text-[10px] opacity-60" data-testid="run-state">{r.state}</span></span>
        <span className="muted text-sm">{formatDate(r.created_at)}</span>
      </div>

      {/* Progreso humano mientras investiga */}
      {!finished && r.state !== "PARTIAL" && r.state !== "FAILED" && r.state !== "CANCELLED" && (
        <section className="mx-auto mt-8 max-w-5xl">
          <div className="rs-bar"><span style={{ width: `${Math.round(((stepIdx + (running ? 0.5 : 0)) / STEPS.length) * 100)}%` }} /></div>
          <ol className="rs-steps mt-4" aria-label="Progreso de la investigación">
            {STEPS.map((s, i) => (
              <li key={s.label} className={`rs-step ${i < stepIdx ? "rs-done" : i === stepIdx ? "rs-now" : ""}`}>
                <span className="rs-icon" aria-hidden="true">{i < stepIdx ? "✓" : s.icon}</span>{s.label}
              </li>))}
          </ol>
          {feed.length > 0 && (
            <ul className="rs-feed prose-left mx-auto mt-6 max-w-3xl space-y-2 text-sm" aria-live="polite">
              {feed.map((e) => <li key={e.id} className="card px-4 py-2"><span className="muted mr-2">{new Date(e.created_at).toLocaleTimeString("es")}</span>{e.message}</li>)}
            </ul>)}
        </section>)}

      {r.state === "AWAITING_APPROVAL" && <p className="mt-4 text-sm">Esta investigación necesita la aprobación del propietario antes de continuar.</p>}
      {r.state === "FAILED" && (
        <div className="card mx-auto mt-6 max-w-2xl p-5" role="alert">
          <p className="text-lg font-semibold">La investigación no pudo completarse</p>
          {isOwner && r.error && <p className="muted mt-1 text-sm">{r.error}</p>}
          <Link className="btn btn-primary mt-4" href="/investigar">Intentarlo de nuevo</Link>
        </div>)}
      {r.result?.no_evidence && (
        <div className="card mx-auto mt-6 max-w-3xl p-5" role="status" data-testid="no-evidence">
          <p className="text-lg font-semibold">Sin evidencia suficiente</p>
          <p className="mt-1 text-sm">{r.result.message}</p>
          {r.result.suggestions && <ul className="list-disc mt-2 pl-5 text-sm">{r.result.suggestions.map((x) => <li key={x}>{x}</li>)}</ul>}
          <p className="muted mt-2 text-xs">Ciencia y Dios no genera contenido sin fuentes verificables.</p>
        </div>)}

      {/* Acciones */}
      <div className="mt-6 flex flex-wrap justify-center gap-2">
        {r.result?.experience_id && <Link data-testid="open-experience" className="btn btn-primary" href={`/experiencias/${r.result.experience_id}`}>Abrir experiencia completa →</Link>}
        {isOwner && r.state === "READY" && <button className="btn btn-primary" data-testid="publish" onClick={() => act("publish")}>Aprobar y publicar</button>}
        {isOwner && r.state === "AWAITING_APPROVAL" && <button className="btn btn-primary" onClick={() => act("approve")}>Aprobar</button>}
        {["PAUSED", "BUDGET_EXHAUSTED"].includes(r.state) && <button className="btn" onClick={() => act("resume")}>Reanudar</button>}
        {running && <button className="btn" onClick={() => act("cancel")}>Cancelar</button>}
      </div>
      {err && <p role="alert" className="mt-2 text-sm text-rose-700">{err}</p>}

      {/* El conocimiento: Cronosfera */}
      {exp && (
        <section className="mt-10">
          <h2 className="text-3xl">Lo que dicen las fuentes</h2>
          <p className="muted mx-auto mt-1 max-w-2xl text-base">Cada punto es un hecho respaldado por citas literales comprobadas. Toca uno para ver sus fuentes y las posturas que lo discuten.</p>
          <div className="mt-6"><Chronosphere packet={exp.knowledge_packet} titles={titles} /></div>
          {exp.knowledge_packet.uncertainties.length > 0 && (
            <div className="card prose-left mx-auto mt-8 max-w-3xl p-5">
              <h3 className="text-lg">Lo que todavía no sabemos</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm">{exp.knowledge_packet.uncertainties.map((u) => <li key={u}>{u}</li>)}</ul>
            </div>)}
        </section>)}

      {/* Solo propietario: la maquinaria */}
      {isOwner && (
        <details className="card prose-left mx-auto mt-12 max-w-6xl p-4 text-left">
          <summary className="cursor-pointer font-semibold">Detalles técnicos (solo propietario)</summary>
          <p className="mt-3 text-sm">Gasto {formatUsd(r.spent_usd)} / presupuesto {formatUsd(r.budget_usd)} · estimado {formatUsd(r.estimated_usd)}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {running && !["PAUSED", "AWAITING_APPROVAL", "BUDGET_EXHAUSTED"].includes(r.state) && <button className="btn" onClick={() => act("pause")}>Pausar</button>}
            {r.state === "BUDGET_EXHAUSTED" && <button className="btn" onClick={() => { const v = prompt("Nuevo presupuesto (USD)", r.budget_usd); if (v) act("budget", { budget_usd: v }); }}>Ajustar presupuesto</button>}
          </div>
          <ol className="mt-4 flex flex-wrap gap-1 text-[11px]" aria-label="Cadena de estados">
            {d.state_chain.map((s) => <li key={s} className={`rounded px-2 py-1 ${s === r.state ? "bg-amber-500 text-white" : "bg-stone-200 dark:bg-stone-800"}`}>{s}</li>)}
          </ol>
          {r.error && <p className="mt-3 text-sm text-rose-700">Error: {r.error}</p>}
          <h3 className="mt-6 text-base font-semibold">Plan (DAG) y tareas</h3>
          <div className="mt-2 overflow-x-auto">
            <table className="w-full text-sm">
              <thead><tr className="text-left muted"><th className="p-1">Tarea</th><th className="p-1">Agente</th><th className="p-1">Fase</th><th className="p-1">Depende de</th><th className="p-1">Estado</th><th className="p-1">Intentos</th><th className="p-1">Coste</th></tr></thead>
              <tbody>{d.tasks.map((t) => (
                <tr key={t.task_key} className="border-t" style={{ borderColor: "var(--line)" }} data-testid={`task-${t.task_key}`}>
                  <td className="p-1 font-mono text-xs">{t.task_key}</td><td className="p-1">{t.agent_code} <span className="muted">v{t.agent_version}</span></td>
                  <td className="p-1">{t.phase}</td><td className="p-1 text-xs">{t.depends_on.join(", ") || "—"}</td>
                  <td className="p-1"><span className={`mr-1 inline-block h-2 w-2 rounded-full ${STATUS_COLOR[t.status] ?? "bg-stone-400"}`} />{t.status}{t.error ? ` — ${t.error}` : ""}</td>
                  <td className="p-1">{t.attempts}</td><td className="p-1">{formatUsd(t.cost_usd)}</td>
                </tr>))}</tbody>
            </table>
          </div>
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            <section>
              <div className="flex items-center justify-between"><h3 className="text-base font-semibold">Traza (SSE)</h3>
                <label className="text-xs"><input type="checkbox" checked={showDebug} onChange={(e) => setShowDebug(e.target.checked)} /> llamadas a herramientas</label></div>
              <ol className="card mt-2 max-h-96 space-y-1 overflow-y-auto p-3 font-mono text-[11px]">
                {events.filter((e) => showDebug || e.level !== "debug").map((e) => (
                  <li key={e.id} className={e.level === "error" ? "text-rose-600" : e.level === "warning" ? "text-amber-600" : ""}>
                    {new Date(e.created_at).toLocaleTimeString("es")} [{e.level}] {e.task_key ? `${e.task_key}: ` : ""}{e.message}
                  </li>))}
              </ol>
            </section>
            <section>
              <h3 className="text-base font-semibold">Costes registrados</h3>
              <table className="card mt-2 w-full text-xs"><tbody>{d.costs.map((c, i) => (
                <tr key={i} className="border-t" style={{ borderColor: "var(--line)" }}><td className="p-1">{c.kind}</td><td className="p-1">{c.agent_code ?? "plan"}</td>
                  <td className="p-1">{c.provider}/{c.model}</td><td className="p-1">{formatUsd(c.amount_usd)}</td><td className="p-1 muted">{c.cache_hit ? "caché · " : ""}{c.note}</td></tr>))}</tbody></table>
              <h3 className="mt-6 text-base font-semibold">Checkpoints</h3>
              <ul className="mt-2 text-xs">{d.checkpoints.map((c) => <li key={c.task_key} className="font-mono">{c.task_key} · {c.state} · {c.output_sha256.slice(0, 16)}…</li>)}</ul>
            </section>
          </div>
        </details>)}
    </div>
  );
}
