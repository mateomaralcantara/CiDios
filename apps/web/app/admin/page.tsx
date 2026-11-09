"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api, formatDate, formatUsd } from "@/lib/api";
import { useAuth } from "@/lib/auth";

type Tab = "resumen" | "agentes" | "ejecuciones" | "costes" | "presupuestos" | "calidad" | "usuarios" | "proveedores" | "experiencias";
const TABS: [Tab, string][] = [["resumen", "Resumen"], ["agentes", "Agentes"], ["ejecuciones", "Ejecuciones"], ["costes", "Costes"],
  ["presupuestos", "Presupuestos"], ["calidad", "Calidad de citas"], ["usuarios", "Usuarios"], ["proveedores", "Modelos y conectores"], ["experiencias", "Publicaciones"]];

/* eslint-disable @typescript-eslint/no-explicit-any */
function Table({ rows, cols }: { rows: any[]; cols: [string, string, ((r: any) => React.ReactNode)?][] }) {
  return (
    <div className="overflow-x-auto"><table className="w-full text-sm">
      <thead><tr className="muted text-left">{cols.map(([k, l]) => <th key={k} className="p-1.5">{l}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i} className="border-t align-top" style={{ borderColor: "var(--line)" }}>
        {cols.map(([k, , f]) => <td key={k} className="p-1.5">{f ? f(r) : String(r[k] ?? "—")}</td>)}</tr>)}</tbody>
    </table></div>
  );
}

export default function Admin() {
  const { session, ready } = useAuth();
  const token = session?.token;
  const [tab, setTab] = useState<Tab>("resumen");
  const [loaded, setLoaded] = useState<{ tab: Tab; data: any } | null>(null);
  const data = loaded?.tab === tab ? loaded.data : null;  // nunca renderiza una pestaña con datos de otra
  const [err, setErr] = useState<string | null>(null);
  const path: Record<Tab, string> = { resumen: "overview", agentes: "agents", ejecuciones: "runs", costes: "costs", presupuestos: "budgets",
    calidad: "quality", usuarios: "users", proveedores: "providers", experiencias: "experiences" };
  const load = useCallback(() => {
    if (!token) return;
    setErr(null);
    const current = tab;
    api<any>(`/v1/admin/${path[current]}`, { token }).then((d) => setLoaded({ tab: current, data: d })).catch((e) => setErr(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, token]);
  useEffect(load, [load]);
  const act = async (p: string, method: string, body?: unknown) => {
    try { await api(p, { token, method, body }); load(); } catch (e) { setErr((e as Error).message); }
  };
  if (!ready) return null;
  if (session?.role !== "owner") return <p className="ui">Acceso exclusivo del propietario. <Link className="underline" href="/entrar">Entrar</Link></p>;

  return (
    <div className="ui">
      <h1 className="text-3xl font-bold" style={{ fontFamily: "ui-serif, Georgia, serif" }}>Centro de control</h1>
      <nav className="mt-4 flex flex-wrap gap-1" role="tablist">{TABS.map(([k, l]) => (
        <button key={k} role="tab" aria-selected={tab === k} className={`btn ${tab === k ? "btn-primary" : ""}`} onClick={() => setTab(k)} data-testid={`tab-${k}`}>{l}</button>))}</nav>
      {err && <p role="alert" className="mt-3 text-sm text-rose-700">{err}</p>}
      {!data ? <p className="muted mt-6">Cargando…</p> : <div className="mt-6">
        {tab === "resumen" && (
          <div className="grid gap-4 md:grid-cols-3">
            <div className="card p-4"><h2 className="font-semibold">Gasto</h2><p className="text-2xl">{formatUsd(data.spend.day)} <span className="muted text-sm">hoy</span></p>
              <p className="muted text-sm">{formatUsd(data.spend.month)} este mes · {data.spend.tokens} tokens</p></div>
            <div className="card p-4"><h2 className="font-semibold">Agentes</h2><p className="text-2xl">{data.agents.operational} <span className="muted text-sm">operativos</span></p>
              <p className="muted text-sm">{data.agents.registered} registrados sin implementar · {data.agents.disabled} deshabilitados</p></div>
            <div className="card p-4"><h2 className="font-semibold">Biblioteca</h2><p className="text-2xl">{data.library.claims} <span className="muted text-sm">afirmaciones</span></p>
              <p className="muted text-sm">{data.library.documents} documentos · {data.library.chunks} fragmentos · {data.library.flagged_chunks} marcados por inyección · {data.library.references} referencias</p></div>
            <div className="card p-4 md:col-span-1"><h2 className="font-semibold">Ejecuciones por estado</h2>
              <ul className="mt-2 text-sm">{data.runs_by_state.map((r: any) => <li key={r.state}>{r.state}: {r.count}</li>)}</ul></div>
            <div className="card p-4"><h2 className="font-semibold">Citas</h2>
              <ul className="mt-2 text-sm">{data.citations.map((r: any) => <li key={r.verification_status}>{r.verification_status}: {r.count}</li>)}</ul></div>
            <div className="card p-4"><h2 className="font-semibold">Errores recientes</h2>
              <ul className="mt-2 space-y-1 text-xs">{data.recent_errors.length ? data.recent_errors.map((e: any, i: number) =>
                <li key={i}><Link className="underline" href={`/ejecuciones/${e.run_id}`}>{e.task_key ?? "run"}</Link>: {e.message}</li>) : <li className="muted">Sin errores</li>}</ul></div>
          </div>)}
        {tab === "agentes" && <Table rows={data} cols={[
          ["number", "#"], ["name_es", "Agente"], ["family", "Familia"], ["status", "Estado"], ["version", "Versión"], ["execution_model", "Ejecución"],
          ["allowed_tools", "Herramientas", (r) => <span className="text-xs">{r.allowed_tools.join(", ")}</span>],
          ["unit_cost_usd", "Coste/tarea", (r) => formatUsd(r.unit_cost_usd)], ["max_cost_per_run_usd", "Tope/inv.", (r) => formatUsd(r.max_cost_per_run_usd)],
          ["enabled", "Habilitado", (r) => r.status === "operational"
            ? <button className="btn" data-testid={`toggle-${r.code}`} onClick={() => act(`/v1/admin/agents/${r.code}`, "PATCH", { enabled: !r.enabled })}>{r.enabled ? "Deshabilitar" : "Habilitar"}</button>
            : <span className="muted text-xs">no implementado</span>]]} />}
        {tab === "ejecuciones" && <Table rows={data} cols={[
          ["state", "Estado"], ["prompt", "Consulta", (r) => <Link className="underline" href={`/ejecuciones/${r.id}`}>{String(r.prompt).slice(0, 70)}…</Link>],
          ["spent_usd", "Gasto", (r) => `${formatUsd(r.spent_usd)} / ${formatUsd(r.budget_usd)}`], ["created_at", "Creada", (r) => formatDate(r.created_at)],
          ["actions", "Control", (r) => <span className="flex gap-1">
            {!["READY", "PUBLISHED", "FAILED", "CANCELLED"].includes(r.state) && <><button className="btn" onClick={() => act(`/v1/runs/${r.id}/pause`, "POST")}>Pausar</button>
              <button className="btn" onClick={() => act(`/v1/runs/${r.id}/cancel`, "POST")}>Cancelar</button></>}
            {r.state === "AWAITING_APPROVAL" && <button className="btn btn-primary" onClick={() => act(`/v1/runs/${r.id}/approve`, "POST")}>Aprobar</button>}
            {r.state === "READY" && <button className="btn btn-primary" onClick={() => act(`/v1/runs/${r.id}/publish`, "POST")}>Publicar</button>}</span>]]} />}
        {tab === "costes" && (<div className="space-y-6">
          <section><h2 className="font-semibold">Por agente / modelo</h2><Table rows={data.by_agent} cols={[["agent_code", "Agente"], ["provider", "Proveedor"], ["model", "Modelo"], ["calls", "Llamadas"], ["actual", "Gasto", (r) => formatUsd(r.actual)]]} /></section>
          <section><h2 className="font-semibold">Por investigación</h2><Table rows={data.by_run} cols={[["run_id", "Ejecución", (r) => <Link className="underline font-mono text-xs" href={`/ejecuciones/${r.run_id}`}>{String(r.run_id).slice(0, 8)}</Link>],
            ["estimated", "Estimado", (r) => formatUsd(r.estimated)], ["actual", "Confirmado", (r) => formatUsd(r.actual)], ["tokens", "Tokens"], ["cache_hit", "Caché", (r) => (r.cache_hit ? "sí" : "no")]]} /></section>
          <section><h2 className="font-semibold">Por usuario</h2><Table rows={data.by_user} cols={[["user_id", "Usuario"], ["actual", "Gasto", (r) => formatUsd(r.actual)]]} /></section>
        </div>)}
        {tab === "presupuestos" && (<div>
          <Table rows={data} cols={[["scope", "Ámbito"], ["scope_ref", "Referencia"], ["period", "Periodo"], ["limit_usd", "Límite", (r) => formatUsd(r.limit_usd)],
            ["auto_approve_below_usd", "Aprobación automática bajo", (r) => formatUsd(r.auto_approve_below_usd)], ["active", "Activa"]]} />
          <form className="card mt-4 flex flex-wrap items-end gap-2 p-4 text-sm" onSubmit={(e) => {
            e.preventDefault(); const f = new FormData(e.currentTarget);
            act("/v1/admin/budgets", "PUT", { scope: f.get("scope"), scope_ref: f.get("scope_ref") || "*", period: f.get("period"), limit_usd: f.get("limit_usd"), auto_approve_below_usd: f.get("auto") || "0.5" });
          }}>
            <label>Ámbito<select name="scope" className="input"><option>global</option><option>user</option><option>investigation</option><option>agent</option><option>provider</option></select></label>
            <label>Referencia<input name="scope_ref" className="input" placeholder="*" /></label>
            <label>Periodo<select name="period" className="input"><option>daily</option><option>monthly</option><option>per_run</option></select></label>
            <label>Límite USD<input name="limit_usd" className="input" type="number" step="0.01" min="0" required /></label>
            <label>Auto-aprobar bajo<input name="auto" className="input" type="number" step="0.01" min="0" placeholder="0.50" /></label>
            <button className="btn btn-primary">Guardar política</button>
          </form></div>)}
        {tab === "calidad" && (<div className="space-y-6">
          <p className="text-sm">{data.impartiality_note}</p>
          <section><h2 className="font-semibold">Verificación de evidencias</h2><Table rows={data.evidence} cols={[["verification_status", "Estado"], ["stance", "Postura"], ["count", "Nº"]]} /></section>
          <section><h2 className="font-semibold">Afirmaciones por categoría epistémica</h2><Table rows={data.claims_by_category} cols={[["category", "Categoría"], ["count", "Nº"]]} /></section>
          <section><h2 className="font-semibold">Controversias sin evidencia contraria registrada</h2><Table rows={data.claims_without_challenges} cols={[["slug", "Afirmación"], ["category", "Categoría"]]} /></section>
          <section><h2 className="font-semibold">Últimos controles de calidad</h2><Table rows={data.qa_results} cols={[["run_id", "Ejecución", (r) => String(r.run_id).slice(0, 8)], ["passed", "Superado", (r) => String(r.passed)],
            ["checks", "Comprobaciones", (r) => <span className="text-xs">{r.checks.map((c: any) => `${c.passed ? "✓" : "✗"} ${c.check}`).join(" · ")}</span>]]} /></section>
        </div>)}
        {tab === "usuarios" && <Table rows={data} cols={[["display_name", "Usuario"], ["id", "Id", (r) => <span className="font-mono text-xs">{r.id}</span>], ["role", "Rol"],
          ["set", "Cambiar rol", (r) => r.id === session.userId ? <span className="muted text-xs">tú</span> :
            <select className="input w-auto" value={r.role} onChange={(e) => act(`/v1/admin/users/${r.id}/role`, "PUT", { role: e.target.value })}>
              <option value="user">user</option><option value="editor">editor</option><option value="owner">owner</option></select>]]} />}
        {tab === "proveedores" && (<div className="space-y-6">
          <section><h2 className="font-semibold">Modelos</h2><Table rows={data.models} cols={[["provider", "Proveedor"], ["model", "Modelo"], ["configured", "Configurado", (r) => (r.configured ? "sí" : "no")],
            ["key_hint", "Clave (enmascarada)", (r) => r.key_hint || "—"], ["used_by", "Uso"]]} /></section>
          <section><h2 className="font-semibold">Embeddings</h2><p className="text-sm">{data.embeddings.model} · {data.embeddings.dim} dimensiones · {data.embeddings.neural ? "neuronal" : "léxico local (no neuronal)"}</p></section>
          <section><h2 className="font-semibold">Conectores</h2><Table rows={data.connectors} cols={[["name", "Conector"], ["implemented", "Implementado", (r) => (r.implemented ? "sí" : "pendiente")], ["enabled", "Activo", (r) => (r.enabled ? "sí" : "no")]]} /></section>
          <section><h2 className="font-semibold">Supabase</h2><p className="text-sm">URL: {data.supabase.url || "no configurada"} · secreto JWT: {data.supabase.jwt_secret_configured ? "configurado" : "no"} · JWKS: {data.supabase.jwks_configured ? "configurado" : "no"}</p>
            <p className="muted text-xs">Los secretos nunca se muestran completos ni se envían al navegador.</p></section>
        </div>)}
        {tab === "experiencias" && <Table rows={data} cols={[["title", "Título", (r) => <Link className="underline" href={`/experiencias/${r.id}`}>{r.title}</Link>], ["modality", "Modalidad"], ["status", "Estado"],
          ["knowledge_packet_sha256", "Paquete", (r) => <span className="font-mono text-xs">{String(r.knowledge_packet_sha256).slice(0, 12)}</span>],
          ["published_at", "Publicada", (r) => formatDate(r.published_at)],
          ["run", "Ejecución", (r) => <Link className="underline" href={`/ejecuciones/${r.run_id}`}>ver traza</Link>]]} />}
      </div>}
    </div>
  );
}
