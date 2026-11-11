"use client";
// Renderer de Experience OS: construye la experiencia a partir del ExperienceSpec SIN alterar las afirmaciones
// del KnowledgePacket (los textos mostrados y narrados se leen siempre del paquete por id).
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Chronosphere } from "@/components/Chronosphere";
import { CategoryChip } from "@/components/ClaimCard";
import { IllustrationFigure } from "@/components/Illustration";
import { SchematicMap } from "@/components/SchematicMap";
import { API_URL, api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { STANCE_LABEL, TIER_STYLE, type BibEntry, type Experience, type KnowledgePacket, type Mission, type PacketClaim, type Progress } from "@/lib/types";

function OriginBadge({ c }: { c: PacketClaim }) {
  if (c.origin !== "llm_extracted") return null;
  return <span className="chip border border-dashed" title="Afirmación propuesta por un modelo a partir de citas verificadas literalmente">
    propuesta por IA ({c.generated_by?.model ?? "LLM"}) · pendiente de revisión</span>;
}

function Bibliography({ packet }: { packet: KnowledgePacket }) {
  const bib = packet.bibliography ?? [];
  if (!bib.length) return null;
  const m = packet.bibliography_metrics ?? {};
  const d = packet.dimensions ?? {};
  return (
    <section className="card mx-auto mt-10 max-w-4xl p-5" data-testid="bibliography">
      <h2 className="text-2xl font-semibold">Bibliografía y sustento</h2>
      <p className="ui muted mt-1 text-xs">
        {m.references} referencias · {m.claims_with_peer_reviewed_support_pct ?? 0} % de afirmaciones con respaldo revisado por pares ·
        {" "}{m.claims_with_expert_support_pct ?? 0} % con respaldo de expertos{m.evidence_excluded_retracted ? ` · ${m.evidence_excluded_retracted} citas de obras retractadas excluidas` : ""}
      </p>
      <div className="ui mt-3 grid gap-2 text-xs md:grid-cols-3">
        <div className="card p-2"><strong>1 · Textos publicados</strong><br />{d.published ? `${d.published.documents} obras (${d.published.sources.join(", ")})` : "no consultado"}</div>
        <div className="card p-2"><strong>2 · Expertos del área</strong><br />{d.experts ? (d.experts.experts.length ? d.experts.experts.map((x) => `${x.name} (h=${x.h_index})`).join(", ") : (d.experts.note ?? "ninguno identificado")) : "no consultado"}</div>
        <div className="card p-2"><strong>3 · HARNESS de bibliografía</strong><br />{m.doi_resolved ?? 0} DOI resueltos · {Object.entries(m.by_tier ?? {}).map(([k, v]) => `${v} ${k}`).join(" · ")}</div>
      </div>
      <ol className="prose-left mt-4 space-y-2 text-sm">
        {bib.map((b: BibEntry) => (
          <li key={b.key} id={`ref-${b.key}`} className="flex gap-2">
            <span className="ui font-semibold">[{b.key}]</span>
            <span>{b.apa.replace(/\*/g, "")}{" "}
              <span className={`ui chip ${TIER_STYLE[b.tier] ?? ""}`}>{b.tier_label}</span>
              {b.identifier_check === "resolved" && <span className="ui chip ml-1 bg-stone-100 dark:bg-stone-800">DOI verificado</span>}
              {b.cited_by ? <span className="ui muted ml-1 text-xs">· citada {b.cited_by} veces</span> : null}
            </span>
          </li>))}
      </ol>
      {d.llm && <p className="ui muted mt-3 text-xs">Análisis asistido por {d.llm.model}: {d.llm.accepted} de {d.llm.proposed} afirmaciones propuestas superaron la verificación literal de citas.{d.llm.unanswered ? ` Sin respuesta en las fuentes: ${d.llm.unanswered}` : ""}</p>}
    </section>
  );
}

interface Feedback { question_id: string; correct: boolean; correct_index: number; explanation: string }

function Sources({ c, onClose }: { c: PacketClaim; onClose: () => void }) {
  return (
    <div role="dialog" aria-modal="true" aria-label="Fuentes" className="fixed inset-0 z-40 flex justify-end bg-black/40" onClick={onClose}>
      <aside className="h-full w-full max-w-xl overflow-y-auto p-5" style={{ background: "var(--bg)" }} onClick={(e) => e.stopPropagation()} data-testid="sources-panel">
        <button className="btn ui float-right" onClick={onClose} autoFocus>Cerrar</button>
        <h2 className="text-xl font-semibold">{c.subject ?? c.slug}</h2>
        <div className="ui mt-1 text-xs"><OriginBadge c={c} /></div>
        <p className="mt-2">{c.statement}</p>
        <div className="ui mt-2 flex flex-wrap gap-2 text-xs">
          <CategoryChip category={c.category} label={c.category_label} />
          {c.date && <span className="chip bg-stone-100 dark:bg-stone-800">{c.date.label} · {c.date.precision_label}</span>}
          <span className="muted">Afirmado por: {c.asserted_by} · {c.discipline}</span>
        </div>
        {c.consensus_note && <p className="ui mt-3 text-sm"><strong>Consenso:</strong> {c.consensus_note}</p>}
        {c.insufficient_evidence_note && <p className="ui mt-1 text-sm"><strong>Evidencia insuficiente:</strong> {c.insufficient_evidence_note}</p>}
        {c.future_research_note && <p className="ui mt-1 text-sm"><strong>Qué podría cambiarlo:</strong> {c.future_research_note}</p>}
        <h3 className="ui mt-5 font-semibold">Evidencias ({c.evidence.length})</h3>
        <div className="mt-2 space-y-3">{c.evidence.map((e) => (
          <blockquote key={e.id} className="card p-3 text-sm">
            {e.citation_key ? <span className="ui mr-1 font-semibold">[{e.citation_key}]</span> : null}
            <span className="ui chip mr-2 bg-stone-100 dark:bg-stone-800">{STANCE_LABEL[e.stance]}</span>
            {e.tier ? <span className={`ui chip mr-2 ${TIER_STYLE[e.tier] ?? ""}`}>{e.tier}</span> : null}“{e.fragment}”
            <div className="ui muted mt-2 text-xs">
              Fuente: <Link className="underline" href={`/biblioteca/${e.document.id}`}>{e.document.title}</Link>, «{e.locator}» · licencia {e.document.license_code}
              {e.reference && <><br />Resume: {e.reference.authors.join(", ")}, <em>{e.reference.title}</em>{e.reference.container_title ? `, ${e.reference.container_title}` : ""}{e.reference.year ? ` (${e.reference.year})` : ""}</>}
              <br />Verificación: {e.verification === "fragment_verified" ? "cita literal comprobada" : e.verification}{e.verification_notes.length ? ` — ${e.verification_notes.join("; ")}` : ""}
            </div>
          </blockquote>))}</div>
        {c.perspectives.length > 0 && (<>
          <h3 className="ui mt-5 font-semibold">Perspectivas</h3>
          {c.perspectives.map((p) => <p key={p.label} className="ui mt-2 text-sm"><strong>{p.label}</strong> ({p.tradition}; {p.held_by}): {p.summary}</p>)}
        </>)}
      </aside>
    </div>
  );
}

function MissionPanel({ mission, done, onSubmit }: { mission: Mission; done: boolean; onSubmit: (a: Record<string, number>) => Promise<{ passed: boolean; feedback: Feedback[] }> }) {
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [fb, setFb] = useState<{ passed: boolean; feedback: Feedback[] } | null>(null);
  const [busy, setBusy] = useState(false);
  return (
    <section className="card mt-6 p-5" data-testid="mission">
      <h3 className="text-xl font-semibold">{mission.title} {done && <span className="ui chip bg-emerald-100 text-emerald-900">completada</span>}</h3>
      <p className="ui muted text-sm">{mission.objective}</p>
      <form className="mt-4 space-y-5" onSubmit={async (e) => {
        e.preventDefault(); setBusy(true);
        try { setFb(await onSubmit(answers)); } finally { setBusy(false); }
      }}>
        {mission.questions.map((q, qi) => {
          const f = fb?.feedback.find((x) => x.question_id === q.id);
          return (
            <fieldset key={q.id} data-testid="question">
              <legend className="font-medium">{qi + 1}. {q.prompt}</legend>
              <div className="ui mt-2 grid gap-1">
                {q.options.map((o, oi) => (
                  <label key={oi} className={`flex cursor-pointer items-center gap-2 rounded-md border px-3 py-2 text-sm ${f && oi === f.correct_index ? "border-emerald-500" : ""}`} style={{ borderColor: f && oi === f.correct_index ? undefined : "var(--line)" }}>
                    <input type="radio" name={q.id} value={oi} checked={answers[q.id] === oi} onChange={() => setAnswers({ ...answers, [q.id]: oi })} required /> {o}
                  </label>))}
              </div>
              {f && <p className={`ui mt-2 text-sm ${f.correct ? "text-emerald-700" : "text-rose-700"}`} data-testid="feedback">{f.correct ? "Correcto." : "No es correcto."} {f.explanation}</p>}
            </fieldset>);
        })}
        <button className="btn btn-primary" disabled={busy} data-testid="submit-mission">Comprobar respuestas</button>
        {fb && <p className="ui text-sm font-semibold" role="status" data-testid="mission-result">{fb.passed ? "¡Misión superada! Nueva etapa desbloqueada." : "Aún no: revisa las fuentes de cada evento y vuelve a intentarlo."}</p>}
      </form>
    </section>
  );
}

export default function ExperiencePage() {
  const { id } = useParams<{ id: string }>();
  const { session, ready } = useAuth();
  const token = session?.token;
  const [exp, setExp] = useState<Experience | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [academic, setAcademic] = useState(false);
  const [stageIdx, setStageIdx] = useState(0);
  const [sources, setSources] = useState<PacketClaim | null>(null);
  const [speaking, setSpeaking] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    api<Experience>(`/v1/experiences/${id}`, { token }).then(setExp).catch((e) => setErr(e.message));
    if (token) api<Progress>(`/v1/experiences/${id}/progress`, { token }).then(setProgress).catch(() => null);
  }, [id, token, ready]);

  const claims = useMemo(() => new Map((exp?.knowledge_packet.claims ?? []).map((c) => [c.id, c])), [exp]);
  const spec = exp?.experience_spec;
  const gamified = !!spec?.gamified && !academic;
  const unlocked = gamified ? (progress?.unlocked_stage ?? 0) : Infinity;
  const stage = spec?.stages[stageIdx];
  const titles = useMemo(() => new Map((spec?.events ?? []).map((e) => [e.claim_id, e.title])), [spec]);
  const stageEvents = useMemo(() => (spec?.events ?? []).filter((e) => e.stage_id === stage?.id), [spec, stage]);

  const speak = useCallback((claimId: string) => {
    const c = claims.get(claimId);
    if (!c || typeof window === "undefined" || !("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    if (speaking === claimId) { setSpeaking(null); return; }
    const u = new SpeechSynthesisUtterance(`${c.subject ?? ""}. ${c.date?.label ?? ""}. ${c.statement}`);
    u.lang = "es-ES"; u.onend = () => setSpeaking(null);
    setSpeaking(claimId); window.speechSynthesis.speak(u);
  }, [claims, speaking]);

  const download = async (format: "json" | "markdown") => {
    const res = await fetch(`${API_URL}/v1/experiences/${id}/export?format=${format}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
    const blob = await res.blob();
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = `ciencia-de-dios-${id.slice(0, 8)}.${format === "json" ? "json" : "md"}`; a.click();
  };

  if (err) return <p role="alert" className="ui">{err}</p>;
  if (!exp || !spec) return <p className="ui muted">Cargando…</p>;
  const packet = exp.knowledge_packet;
  const totalMissions = spec.stages.filter((s) => s.mission).length;

  if (spec.modality === "article" || spec.modality === "comparison_matrix") {
    return (
      <article>
        <h1 className="text-3xl font-bold">{spec.title}</h1>
        {spec.sections.map((s) => (
          <section key={s.heading} className="mt-8"><h2 className="text-2xl font-semibold">{s.heading}</h2><p className="muted">{s.intro}</p>
            {s.claim_ids.map((cid) => { const c = claims.get(cid)!; return (
              <div key={cid} className="card mt-3 p-4"><CategoryChip category={c.category} label={c.category_label} /> <OriginBadge c={c} /> {c.date && <span className="ui muted text-xs">{c.date.label}</span>}
                <p className="mt-1">{c.statement}{" "}<span className="ui muted text-xs">{[...new Set(c.evidence.map((e) => e.citation_key).filter(Boolean))].map((k) => `[${k}]`).join("")}</span></p>
                <button className="ui mt-2 text-sm underline" onClick={() => setSources(c)}>Fuentes ({c.evidence.length})</button></div>); })}
          </section>))}
        <Bibliography packet={exp.knowledge_packet} />
        {sources && <Sources c={sources} onClose={() => setSources(null)} />}
      </article>
    );
  }

  return (
    <div>
      <p className="ui accent text-sm font-semibold">{spec.gamified ? "Línea de tiempo ilustrada y gamificada" : "Línea de tiempo"} · {exp.status}</p>
      <h1 className="text-4xl font-bold">{spec.title}</h1>
      <p className="ui muted mt-2 text-xs break-all">KnowledgePacket {packet.packet_version} · sha256 {packet.sha256.slice(0, 20)}… · {packet.claims.length} afirmaciones verificadas · ExperienceSpec {spec.spec_version}</p>

      <div className="ui mt-4 flex flex-wrap items-center gap-2">
        {spec.gamified && (
          <div role="group" aria-label="Modo" className="flex gap-1">
            <button className={`btn ${!academic ? "btn-primary" : ""}`} onClick={() => setAcademic(false)} data-testid="mode-game">Modo misión</button>
            <button className={`btn ${academic ? "btn-primary" : ""}`} onClick={() => setAcademic(true)} data-testid="mode-academic">Modo académico</button>
          </div>)}
        <button className="btn" onClick={() => download("markdown")}>Exportar (Markdown)</button>
        <button className="btn" onClick={() => download("json")}>Exportar (JSON)</button>
        {gamified && (
          <span className="text-sm" data-testid="progress">Progreso: {progress?.completed_missions.length ?? 0}/{totalMissions} misiones · {progress?.score ?? 0} puntos
            {!session && <> · <Link className="underline" href="/entrar">entra</Link> para guardar tu progreso</>}</span>)}
      </div>
      <ul className="ui muted mt-3 list-disc pl-5 text-xs">{spec.notices.map((n) => <li key={n}>{n}</li>)}</ul>

      <section className="mt-8" aria-label="Cronosfera">
        <Chronosphere packet={packet} titles={titles} />
      </section>
      <h2 className="mt-12 text-2xl">Recorrido por etapas</h2>

      <nav className="ui mt-6 flex flex-wrap justify-center gap-2 pb-2" aria-label="Etapas">
        {spec.stages.map((s, i) => {
          const locked = i > unlocked;
          const done = progress?.completed_missions.includes(s.mission?.id ?? "");
          return (
            <button key={s.id} disabled={locked} onClick={() => setStageIdx(i)} data-testid={`stage-${i}`}
              className={`card min-w-44 shrink-0 p-3 text-center text-sm ${i === stageIdx ? "ring-2 ring-amber-500" : ""} ${locked ? "opacity-50" : ""}`}>
              <span className="block text-xs muted">{locked ? "🔒 Bloqueada" : done && gamified ? "✓ Superada" : `Etapa ${i + 1}`} · {s.range_label}</span>
              <span className="font-semibold">{s.title}</span>
            </button>);
        })}
      </nav>

      {stage && (
        <div className="mt-4 grid gap-6 lg:grid-cols-[1fr_380px]">
          <section>
            <p className="text-lg">{stage.intro}</p>
            <ol className="relative mx-auto mt-6 max-w-3xl space-y-5">
              {stageEvents.map((e) => {
                const c = claims.get(e.claim_id)!;
                return (
                  <li key={e.claim_id} className="card relative p-4" data-testid="timeline-event">
                    <div className="ui flex flex-wrap items-center gap-2 text-xs">
                      <span className="chip bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900">{e.date_label}</span>
                      <span className="muted">precisión: {c.date?.precision_label}</span>
                      <CategoryChip category={c.category} label={c.category_label} />
                      {e.place_name && <span className="muted">📍 {e.place_name}</span>}
                    </div>
                    <h3 className="mt-2 text-xl font-semibold">{e.title}</h3>
                    <p className="mt-1">{c.statement}</p>
                    {c.insufficient_evidence_note && <p className="ui mt-1 text-sm text-amber-700 dark:text-amber-400">⚠ {c.insufficient_evidence_note}</p>}
                    <div className="mt-3"><IllustrationFigure ill={e.illustration} /></div>
                    <div className="ui mt-3 flex flex-wrap gap-2">
                      <button className="btn" onClick={() => setSources(c)} data-testid="open-sources">Fuentes ({c.evidence.length})</button>
                      <button className="btn" onClick={() => speak(e.claim_id)} aria-pressed={speaking === e.claim_id}>{speaking === e.claim_id ? "Detener narración" : "Narrar"}</button>
                    </div>
                  </li>);
              })}
            </ol>
            {gamified && stage.mission && (
              session ? (
                <MissionPanel key={stage.mission.id} mission={stage.mission} done={!!progress?.completed_missions.includes(stage.mission.id)}
                  onSubmit={async (answers) => {
                    const r = await api<{ passed: boolean; feedback: Feedback[]; progress: Progress }>(`/v1/experiences/${id}/missions`,
                      { token, body: { mission_id: stage.mission!.id, answers } });
                    setProgress((p) => ({ ...(p ?? { answers: {} }), ...r.progress } as Progress));
                    return r;
                  }} />
              ) : <p className="ui card mt-6 p-4 text-sm"><Link className="underline" href="/entrar">Entra</Link> para realizar la misión de esta etapa y guardar tu progreso.</p>
            )}
          </section>
          <aside className="space-y-4">
            {spec.map && <SchematicMap map={spec.map} active={new Set(stage.event_claim_ids)} />}
            <div className="card p-4">
              <h2 className="font-semibold">Incertidumbres reconocidas</h2>
              <ul className="ui mt-2 list-disc space-y-1 pl-4 text-xs">{packet.uncertainties.map((u) => <li key={u}>{u}</li>)}</ul>
            </div>
            <div className="card p-4">
              <h2 className="font-semibold">Contexto sin fecha</h2>
              {packet.claims.filter((c) => !c.is_event || !c.date).map((c) => (
                <div key={c.id} className="mt-3 text-sm"><CategoryChip category={c.category} label={c.category_label} />
                  <p className="mt-1">{c.statement}</p><button className="ui text-xs underline" onClick={() => setSources(c)}>Fuentes</button></div>))}
            </div>
            <div className="card p-4">
              <h2 className="font-semibold">Limitaciones de esta investigación</h2>
              <ul className="ui mt-2 list-disc space-y-1 pl-4 text-xs">{packet.limitations.map((u) => <li key={u}>{u}</li>)}</ul>
            </div>
          </aside>
        </div>
      )}
      <Bibliography packet={packet} />
      {sources && <Sources c={sources} onClose={() => setSources(null)} />}
    </div>
  );
}
