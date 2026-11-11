"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, formatDate } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const EXAMPLE = "Investiga la historia de la transmisión de los textos bíblicos desde sus testimonios antiguos hasta las ediciones modernas. Muéstrame las evidencias arqueológicas y textuales, las posiciones académicas relevantes, las dataciones conocidas y las incertidumbres. Convierte la investigación en una línea de tiempo ilustrada y gamificada, con mapas, fuentes consultables, misiones pedagógicas, preguntas interactivas y narración opcional";

const STATE_LABEL: Record<string, string> = {
  READY: "Lista", PUBLISHED: "Publicada", FAILED: "No completada", CANCELLED: "Cancelada", PARTIAL: "Sin evidencia",
  PAUSED: "En pausa", AWAITING_APPROVAL: "Esperando aprobación", BUDGET_EXHAUSTED: "Detenida",
};

interface Inv { id: string; prompt: string; status: string; created_at: string; run_id: string; state: string; spent_usd: string; result: { experience_id?: string } }

export default function Investigar() {
  const { session, ready } = useAuth();
  const router = useRouter();
  const [prompt, setPrompt] = useState(EXAMPLE);
  const [modality, setModality] = useState("");
  const [level, setLevel] = useState("general");
  const [list, setList] = useState<Inv[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (session) api<Inv[]>("/v1/investigations", { token: session.token }).then(setList).catch(() => null); }, [session]);
  if (ready && !session) return <p className="ui">Necesitas <Link className="underline" href="/entrar">entrar</Link> para investigar.</p>;
  return (
    <div>
      <h1 className="text-3xl font-bold">Nueva investigación</h1>
      <p className="muted mt-2 max-w-3xl">Haz una pregunta. Buscaremos en textos publicados y en la obra de los expertos del área, contrastaremos las posturas, comprobaremos cada cita palabra por palabra y lo convertiremos en una línea de tiempo que puedes explorar.</p>
      <form className="ui card mt-6 space-y-3 p-5" onSubmit={async (e) => {
        e.preventDefault(); setErr(null); setBusy(true);
        try {
          const prefs: Record<string, string> = { level };
          if (modality) prefs.modality = modality;
          const r = await api<{ run_id: string; reused: boolean }>("/v1/investigations", { token: session!.token, body: { prompt, preferences: prefs } });
          router.push(`/ejecuciones/${r.run_id}${r.reused ? "?reutilizada=1" : ""}`);
        } catch (er) { setErr((er as Error).message); setBusy(false); }
      }}>
        <label className="block text-sm font-semibold" htmlFor="prompt">Pregunta o encargo</label>
        <textarea id="prompt" data-testid="prompt" className="input min-h-40" value={prompt} onChange={(e) => setPrompt(e.target.value)} minLength={10} maxLength={4000} required />
        <div className="flex flex-wrap gap-3 text-sm">
          <label>Formato <select className="input mt-1 w-auto" value={modality} onChange={(e) => setModality(e.target.value)}>
            <option value="">Detectar de la consulta</option><option value="article">Artículo enciclopédico</option>
            <option value="comparison_matrix">Matriz comparativa</option><option value="timeline">Línea de tiempo</option>
            <option value="gamified_timeline">Línea de tiempo gamificada</option></select></label>
          <label>Nivel <select className="input mt-1 w-auto" value={level} onChange={(e) => setLevel(e.target.value)}>
            <option value="general">General</option><option value="secundaria">Secundaria</option><option value="universitario">Universitario</option><option value="especialista">Especialista</option></select></label>
        </div>
        <p className="muted text-xs">Modalidades disponibles en esta versión: artículo, matriz comparativa, línea de tiempo y línea de tiempo gamificada. Las demás se planificarán cuando sus agentes estén operativos.</p>
        <button className="btn btn-primary" data-testid="launch" disabled={busy}>{busy ? "Lanzando…" : "Investigar"}</button>
        {err && <p role="alert" className="text-sm text-rose-700">{err}</p>}
      </form>
      <h2 className="mb-3 mt-10 text-2xl font-semibold">Mis investigaciones</h2>
      <div className="ui space-y-2">{list.map((i) => (
        <div key={i.id} className="card flex flex-wrap items-center gap-3 p-3 text-sm">
          <span className="chip bg-stone-100 dark:bg-stone-800">{STATE_LABEL[i.state] ?? "Investigando…"}</span>
          <span className="flex-1 truncate" title={i.prompt}>{i.prompt}</span>
          <span className="muted">{formatDate(i.created_at)}</span>
          <Link className="underline" href={`/ejecuciones/${i.run_id}`}>Ver investigación</Link>
          {i.result?.experience_id && <Link className="accent underline" href={`/experiencias/${i.result.experience_id}`}>Experiencia</Link>}
        </div>))}</div>
    </div>
  );
}
