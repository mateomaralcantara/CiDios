"use client";
// CRONOSFERA — línea de tiempo de CIENCIA Y DIOS.
// · Escala elástica: el orden temporal se respeta, pero los siglos vacíos se comprimen y las épocas densas se abren.
// · Halo de incertidumbre: la anchura del halo sobre el eje es el intervalo real de la datación (lo que NO sabemos).
// · Orbes por categoría epistémica, del tamaño de su respaldo documental.
// · Pasar el ratón despliega en la propia tarjeta TODO lo que se sabe (con barra lateral para subir y bajar);
//   hacer clic abre la lente grande con citas literales, fuentes y posturas.
// Solo lee el KnowledgePacket: nunca altera afirmaciones.
import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { STANCE_LABEL, type BibEntry, type KnowledgePacket, type PacketClaim } from "@/lib/types";

export const CATEGORY_COLOR: Record<string, string> = {
  empirical_fact: "#10b981", historical_document: "#0ea5e9", scholarly_consensus: "#6366f1",
  scientific_hypothesis: "#8b5cf6", philosophical_argument: "#d946ef", theological_interpretation: "#f59e0b",
  religious_belief: "#f97316", contested: "#f43f5e", uncorroborated: "#78716c", open_question: "#eab308",
};
const colorOf = (c: string) => CATEGORY_COLOR[c] ?? "#a8a29e";

export function formatYear(y: number): string {
  if (y < 0) return `${Math.abs(y).toLocaleString("es")} a. C.`;
  return y < 1000 ? `${y} d. C.` : String(y);
}

interface Item { c: PacketClaim; title: string; start: number; end: number; x: number; x2: number; lane: 0 | 1; sources: number }

const PAD = 190;          // margen a cada lado del eje
const MIN_GAP = 150;      // separación mínima entre hechos consecutivos (px)
const STRETCH = 46;       // cuánto «pesa» el tiempo transcurrido (logarítmico)
const HEIGHT = 840;          // alto suficiente para que la tarjeta desplegada quepa entera
const STEM = 62;          // tallo entre el eje y la tarjeta
const AXIS = HEIGHT / 2;
const CARD_MAX = AXIS - STEM - 14;   // alto máximo de una tarjeta desplegada

function layout(claims: PacketClaim[], titles: Map<string, string>): { items: Item[]; width: number } {
  const dated = claims
    .filter((c) => c.date && c.date.start !== null && c.date.start !== undefined)
    .map((c) => ({ c, start: c.date!.start as number, end: (c.date!.end ?? c.date!.start) as number }))
    .sort((a, b) => a.start - b.start || a.end - b.end);
  const anchors: { year: number; x: number }[] = [];
  let x = PAD;
  dated.forEach((d, i) => {
    const prev = dated[i - 1];
    if (prev) x += MIN_GAP + STRETCH * Math.log1p(Math.max(0, d.start - prev.start) / 10);
    anchors.push({ year: d.start, x });
  });
  // posición de cualquier año (para el final de los intervalos): interpolación monótona entre anclas
  const at = (year: number): number => {
    const head = anchors[0], last = anchors[anchors.length - 1];
    if (!head || !last) return PAD;
    if (year <= head.year) return head.x;
    for (let i = 1; i < anchors.length; i++) {
      const a = anchors[i - 1]!, b = anchors[i]!;
      if (year <= b.year) return b.year === a.year ? b.x : a.x + ((year - a.year) / (b.year - a.year)) * (b.x - a.x);
    }
    return last.x + STRETCH * Math.log1p((year - last.year) / 10);
  };
  const items = dated.map((d, i) => ({
    c: d.c, start: d.start, end: d.end, x: anchors[i]!.x, x2: Math.max(anchors[i]!.x, at(d.end)), lane: (i % 2) as 0 | 1,
    title: titles.get(d.c.id) || d.c.subject || d.c.statement.slice(0, 70),
    sources: new Set(d.c.evidence.map((e) => e.citation_key ?? e.document.id)).size,
  }));
  const width = (items.length ? Math.max(...items.map((i) => i.x2)) : PAD) + PAD;
  return { items, width };
}

// Barra lateral propia de la tarjeta: ▲ ▼, pista clicable y asa arrastrable (también funciona la rueda del ratón)
function ScrollRail({ target }: { target: React.RefObject<HTMLDivElement | null> }) {
  const [m, setM] = useState({ top: 0, size: 1 });
  const sync = useCallback(() => {
    const el = target.current;
    if (!el) return;
    const size = el.scrollHeight > 0 ? Math.min(1, el.clientHeight / el.scrollHeight) : 1;
    const top = el.scrollHeight > el.clientHeight ? el.scrollTop / (el.scrollHeight - el.clientHeight) : 0;
    setM({ top, size });
  }, [target]);
  useEffect(() => {
    const el = target.current;
    if (!el) return;
    sync();
    el.addEventListener("scroll", sync);
    const ro = new ResizeObserver(sync); ro.observe(el);
    return () => { el.removeEventListener("scroll", sync); ro.disconnect(); };
  }, [target, sync]);
  const by = (dy: number) => target.current?.scrollBy({ top: dy, behavior: "smooth" });
  const stop = (e: React.SyntheticEvent) => e.stopPropagation();
  if (m.size >= 0.999) return null;
  return (
    <div className="cs-rail" onPointerDown={stop} onClick={stop}>
      <button type="button" className="cs-rail-btn" aria-label="Subir" onClick={() => by(-140)}>▲</button>
      <div className="cs-rail-track" onPointerDown={(e) => {
        const el = target.current; if (!el) return;
        const r = e.currentTarget.getBoundingClientRect();
        el.scrollTo({ top: ((e.clientY - r.top) / r.height) * el.scrollHeight - el.clientHeight / 2, behavior: "smooth" });
      }}>
        <span className="cs-rail-thumb" style={{ height: `${m.size * 100}%`, top: `${m.top * (1 - m.size) * 100}%` }}
          onPointerDown={(e) => {
            e.stopPropagation();
            const el = target.current, track = e.currentTarget.parentElement; if (!el || !track) return;
            const y0 = e.clientY, s0 = el.scrollTop, ratio = el.scrollHeight / track.clientHeight;
            const move = (ev: PointerEvent) => { el.scrollTop = s0 + (ev.clientY - y0) * ratio; };
            const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
            window.addEventListener("pointermove", move); window.addEventListener("pointerup", up);
          }} />
      </div>
      <button type="button" className="cs-rail-btn" aria-label="Bajar" onClick={() => by(140)}>▼</button>
    </div>
  );
}

// Tarjeta de la línea de tiempo: compacta en reposo; al pasar el ratón muestra TODO lo que se sabe del hecho
function EventCard({ it, bib, up, active, onOpen }: { it: Item; bib: Map<number, BibEntry>; up: boolean; active: boolean; onOpen: () => void }) {
  const c = it.c;
  const color = colorOf(c.category);
  const body = useRef<HTMLDivElement>(null);
  const span = it.end - it.start;
  return (
    <div role="button" tabIndex={0} className={`cs-card ${up ? "cs-up" : "cs-down"}`} data-testid="chrono-event" aria-expanded={active}
      aria-label={`${c.date?.label}: ${it.title}`}
      style={{ left: it.x - 120, ["--card-max" as string]: `${CARD_MAX}px`, ...(up ? { bottom: HEIGHT - AXIS + STEM } : { top: AXIS + STEM }) }}
      onClick={onOpen} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onOpen(); } }}
      onMouseLeave={() => body.current?.scrollTo({ top: 0 })}>
      <span className="cs-card-date">{c.date?.label}</span>
      <span className="cs-card-title">{it.title}</span>
      <div className="cs-card-body">
        <div ref={body} className="cs-card-scroll" onWheel={(e) => e.stopPropagation()}>
          <p className="cs-card-statement">{c.statement}</p>
          <div className="cs-card-more">
            <dl className="cs-facts">
              <div><dt>Fecha</dt><dd>{c.date?.label} · {c.date?.precision_label}</dd></div>
              {span > 0 && <div><dt>Margen</dt><dd>{formatYear(it.start)} – {formatYear(it.end)} ({span.toLocaleString("es")} años)</dd></div>}
              {c.place?.name && <div><dt>Lugar</dt><dd>{c.place.name}</dd></div>}
              <div><dt>Tipo</dt><dd>{c.category_label}</dd></div>
              <div><dt>Disciplina</dt><dd>{c.discipline}</dd></div>
              <div><dt>Lo sostiene</dt><dd>{c.asserted_by}</dd></div>
            </dl>
            {c.consensus_note && <p className="cs-card-note"><strong>Consenso.</strong> {c.consensus_note}</p>}
            {c.insufficient_evidence_note && <p className="cs-card-note cs-card-warn"><strong>Lo que no sabemos.</strong> {c.insufficient_evidence_note}</p>}
            {c.future_research_note && <p className="cs-card-note"><strong>Qué podría cambiarlo.</strong> {c.future_research_note}</p>}
            <p className="cs-card-h">Evidencia literal ({c.evidence.length})</p>
            {c.evidence.map((e) => {
              const b = e.citation_key ? bib.get(e.citation_key) : undefined;
              return (
                <blockquote key={e.id} className="cs-card-quote">“{e.fragment}”
                  <span className="cs-card-src">{STANCE_LABEL[e.stance]}{e.citation_key ? ` · [${e.citation_key}]` : ""} ·{" "}
                    {b ? `${b.authors.slice(0, 2).join(", ")}${b.authors.length > 2 ? " et al." : ""}${b.year ? ` (${b.year})` : ""}. ${b.title}` : e.document.title}
                    {e.locator ? ` · «${e.locator}»` : ""}</span>
                </blockquote>);
            })}
            {c.perspectives.length > 0 && <p className="cs-card-h">Posturas ({c.perspectives.length})</p>}
            {c.perspectives.map((p) => (
              <p key={p.label} className="cs-card-note"><strong>{p.label}</strong> <span className="cs-card-src">({p.tradition}{p.held_by ? `; ${p.held_by}` : ""})</span><br />{p.summary}</p>))}
            {c.origin === "llm_extracted" && <p className="cs-card-src">Propuesta a partir de citas verificadas · pendiente de revisión</p>}
            <p className="cs-card-open">Haz clic para verlo en grande →</p>
          </div>
        </div>
        <ScrollRail target={body} />
      </div>
      <span className="cs-card-meta"><span className="cs-dot" style={{ background: color }} />{c.category_label} · {it.sources} {it.sources === 1 ? "fuente" : "fuentes"}</span>
    </div>
  );
}

function Lens({ item, bib, onPrev, onNext, onClose, index, total }: {
  item: Item; bib: Map<number, BibEntry>; onPrev: () => void; onNext: () => void; onClose: () => void; index: number; total: number;
}) {
  const c = item.c;
  const color = colorOf(c.category);
  const span = item.end - item.start;
  return (
    <section className="cs-lens card prose-left mt-6 overflow-hidden text-left" style={{ ["--cs" as string]: color }}
      role="region" aria-live="polite" aria-label={`Detalle: ${item.title}`} data-testid="chrono-lens" key={c.id}>
      <div className="cs-lens-bar" />
      <div className="grid gap-6 p-5 sm:p-7 lg:grid-cols-[240px_1fr]">
        <aside className="ui">
          <p className="text-xs font-semibold uppercase tracking-[0.14em]" style={{ color }}>{c.category_label}</p>
          <p className="mt-2 text-3xl font-bold leading-tight" style={{ fontFamily: "var(--font-serif)" }}>{c.date?.label}</p>
          <p className="muted mt-1 text-sm">Precisión: {c.date?.precision_label}</p>
          {span > 0 && <p className="mt-3 text-sm"><span className="cs-halo-key" /> Margen de {span.toLocaleString("es")} años</p>}
          {c.place?.name && <p className="mt-3 text-sm">📍 {c.place.name}</p>}
          <p className="muted mt-3 text-sm">{c.discipline} · {c.asserted_by}</p>
          {c.origin === "llm_extracted" && <p className="mt-3 text-xs"><span className="chip border border-dashed">pendiente de revisión</span></p>}
          <div className="mt-5 flex gap-2">
            <button className="btn px-3" onClick={onPrev} disabled={index === 0} aria-label="Hecho anterior">←</button>
            <button className="btn px-3" onClick={onNext} disabled={index === total - 1} aria-label="Hecho siguiente">→</button>
            <button className="btn px-3" onClick={onClose} aria-label="Cerrar">✕</button>
          </div>
          <p className="muted mt-2 text-xs">{index + 1} de {total} · usa ← → en el teclado</p>
        </aside>
        <div>
          <h3 className="text-2xl">{item.title}</h3>
          <p className="mt-3 text-xl leading-relaxed">{c.statement}</p>
          {(c.consensus_note || c.insufficient_evidence_note || c.future_research_note) && (
            <div className="ui mt-4 grid gap-2 text-sm sm:grid-cols-3">
              {c.consensus_note && <div className="cs-note"><strong>Consenso</strong><br />{c.consensus_note}</div>}
              {c.insufficient_evidence_note && <div className="cs-note cs-note-warn"><strong>Lo que no sabemos</strong><br />{c.insufficient_evidence_note}</div>}
              {c.future_research_note && <div className="cs-note"><strong>Qué podría cambiarlo</strong><br />{c.future_research_note}</div>}
            </div>)}
          <h4 className="ui mt-6 text-sm font-semibold uppercase tracking-[0.12em] muted">Evidencia literal ({c.evidence.length})</h4>
          <div className="mt-2 space-y-3">
            {c.evidence.map((e) => {
              const b = e.citation_key ? bib.get(e.citation_key) : undefined;
              return (
                <blockquote key={e.id} className="cs-quote">
                  <p>“{e.fragment}”</p>
                  <div className="ui muted mt-2 text-left text-xs not-italic">
                    <span className="chip mr-2 bg-stone-100 dark:bg-stone-800">{STANCE_LABEL[e.stance]}</span>
                    {e.citation_key ? <strong className="mr-1">[{e.citation_key}]</strong> : null}
                    {b ? <>{b.authors.slice(0, 2).join(", ")}{b.authors.length > 2 ? " et al." : ""}{b.year ? ` (${b.year})` : ""}. <em>{b.title}</em>{b.tier_label ? ` · ${b.tier_label}` : ""}</>
                      : <Link className="underline" href={`/biblioteca/${e.document.id}`}>{e.document.title}</Link>}
                    {e.locator ? ` · «${e.locator}»` : ""}
                  </div>
                </blockquote>);
            })}
          </div>
          {c.perspectives.length > 0 && (<>
            <h4 className="ui mt-6 text-sm font-semibold uppercase tracking-[0.12em] muted">Posturas</h4>
            <div className="mt-2 grid gap-3 sm:grid-cols-2">
              {c.perspectives.map((p) => (
                <div key={p.label} className="cs-voice"><p className="ui text-sm font-semibold">{p.label}</p>
                  <p className="ui muted text-xs">{p.tradition}{p.held_by ? ` · ${p.held_by}` : ""}</p>
                  <p className="mt-1 text-base">{p.summary}</p></div>))}
            </div></>)}
        </div>
      </div>
    </section>
  );
}

export function Chronosphere({ packet, titles }: { packet: KnowledgePacket; titles?: Map<string, string> }) {
  const titleMap = useMemo(() => titles ?? new Map<string, string>(), [titles]);
  const { items, width } = useMemo(() => layout(packet.claims, titleMap), [packet.claims, titleMap]);
  const bib = useMemo(() => new Map((packet.bibliography ?? []).map((b) => [b.key, b])), [packet.bibliography]);
  const undated = useMemo(() => packet.claims.filter((c) => !c.date || c.date.start === null || c.date.start === undefined), [packet.claims]);
  const cats = useMemo(() => [...new Map(packet.claims.map((c) => [c.category, c.category_label])).entries()], [packet.claims]);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [sel, setSel] = useState<number | null>(null);
  const [extra, setExtra] = useState<PacketClaim | null>(null);   // hecho sin fecha abierto en la lente
  const [playing, setPlaying] = useState(false);
  const [view, setView] = useState({ left: 0, w: 1 });
  const scroller = useRef<HTMLDivElement>(null);
  const drag = useRef<{ x: number; left: number; moved: boolean } | null>(null);

  const focus = useCallback((i: number) => {
    setExtra(null); setSel(i);
    const el = scroller.current, it = items[i];
    if (el && it) el.scrollTo({ left: it.x - el.clientWidth / 2, behavior: "smooth" });
  }, [items]);

  // Recorrido automático
  useEffect(() => {
    if (!playing || !items.length) return;
    const t = setTimeout(() => {
      const next = sel === null ? 0 : sel + 1;
      if (next >= items.length) { setPlaying(false); return; }
      focus(next);
    }, sel === null ? 50 : 6500);
    return () => clearTimeout(t);
  }, [playing, sel, items.length, focus]);

  // Teclado: ← → para moverse, Esc para cerrar
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (sel === null || (e.target as HTMLElement)?.closest("input,textarea,select")) return;
      if (e.key === "ArrowRight" && sel < items.length - 1) { e.preventDefault(); focus(sel + 1); }
      if (e.key === "ArrowLeft" && sel > 0) { e.preventDefault(); focus(sel - 1); }
      if (e.key === "Escape") { setSel(null); setPlaying(false); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sel, items.length, focus]);

  const syncView = useCallback(() => {
    const el = scroller.current;
    if (el) setView({ left: el.scrollLeft / width, w: Math.min(1, el.clientWidth / width) });
  }, [width]);
  useEffect(() => {
    syncView();
    window.addEventListener("resize", syncView);
    return () => window.removeEventListener("resize", syncView);
  }, [syncView]);

  if (!items.length && !undated.length) return null;
  const first = items[0], last = items[items.length - 1];
  const sources = new Set(packet.claims.flatMap((c) => c.evidence.map((e) => e.citation_key ?? e.document.id))).size;
  const perspectives = packet.claims.reduce((n, c) => n + c.perspectives.length, 0);
  const current = sel !== null ? items[sel] : null;

  return (
    <div className="chronosphere" data-testid="chronosphere">
      <div className="ui mx-auto grid max-w-4xl grid-cols-2 gap-3 sm:grid-cols-4">
        {[[items.length, "hechos fechados"], [sources, "fuentes citadas"], [perspectives, "posturas contrastadas"],
          [packet.uncertainties.length, "incertidumbres declaradas"]].map(([n, l]) => (
          <div key={String(l)} className="cs-stat"><span className="cs-stat-n">{n}</span><span className="muted text-xs">{l}</span></div>))}
      </div>

      {items.length > 0 && (<>
        <div className="ui mt-6 flex flex-wrap items-center justify-center gap-2 text-sm">
          <button className="btn btn-primary" onClick={() => { if (playing) setPlaying(false); else { setPlaying(true); if (sel === null || sel >= items.length - 1) setSel(null); } }}
            data-testid="chrono-play">{playing ? "❚❚ Pausar recorrido" : "▶ Recorrer la historia"}</button>
          {first && last && <span className="muted">De <strong>{formatYear(first.start)}</strong> a <strong>{formatYear(last.end)}</strong></span>}
        </div>
        <div className="ui mt-3 flex flex-wrap justify-center gap-2 text-xs" role="group" aria-label="Filtrar por tipo de conocimiento">
          {cats.map(([k, label]) => {
            const off = hidden.has(k);
            return (
              <button key={k} className={`cs-filter ${off ? "cs-filter-off" : ""}`} aria-pressed={!off}
                onClick={() => setHidden((h) => { const n = new Set(h); if (n.has(k)) n.delete(k); else n.add(k); return n; })}>
                <span className="cs-dot" style={{ background: colorOf(k) }} />{label}
              </button>);
          })}
        </div>

        <div className="cs-stage mt-4">
          <button className="cs-nav cs-nav-l" aria-label="Desplazar a la izquierda"
            onClick={() => scroller.current?.scrollBy({ left: -scroller.current.clientWidth * 0.7, behavior: "smooth" })}>‹</button>
          <button className="cs-nav cs-nav-r" aria-label="Desplazar a la derecha"
            onClick={() => scroller.current?.scrollBy({ left: scroller.current.clientWidth * 0.7, behavior: "smooth" })}>›</button>
          <div ref={scroller} className="cs-scroller" onScroll={syncView}
            onPointerDown={(e) => { if (e.pointerType === "mouse") drag.current = { x: e.clientX, left: scroller.current!.scrollLeft, moved: false }; }}
            onPointerMove={(e) => {
              const d = drag.current; if (!d) return;
              if (Math.abs(e.clientX - d.x) > 4) d.moved = true;
              scroller.current!.scrollLeft = d.left - (e.clientX - d.x);
            }}
            onPointerUp={() => { setTimeout(() => { drag.current = null; }, 0); }}
            onPointerLeave={() => { drag.current = null; }}>
            <div className="cs-canvas" style={{ width, height: HEIGHT }}>
              <div className="cs-axis" style={{ top: AXIS, left: PAD / 2, width: width - PAD }} />
              {items.map((it, i) => {
                const color = colorOf(it.c.category);
                const dim = hidden.has(it.c.category);
                const size = Math.min(30, 14 + it.sources * 3);
                const halo = Math.max(size + 14, it.x2 - it.x + size + 14);
                const up = it.lane === 0;
                return (
                  <div key={it.c.id} className={`cs-item ${dim ? "cs-dim" : ""} ${sel === i ? "cs-active" : ""}`} style={{ ["--cs" as string]: color }}>
                    <span className="cs-halo" style={{ left: it.x - (size + 14) / 2, top: AXIS - (size + 14) / 2, width: halo, height: size + 14 }}
                      title={it.end > it.start ? `Intervalo de datación: ${formatYear(it.start)} – ${formatYear(it.end)}` : undefined} />
                    <span className="cs-stem" style={{ left: it.x - 1, top: up ? AXIS - STEM : AXIS, height: STEM }} />
                    <button className="cs-orb" style={{ left: it.x - size / 2, top: AXIS - size / 2, width: size, height: size }}
                      aria-label={`${it.c.date?.label}: ${it.title}`} tabIndex={-1}
                      onClick={() => { if (!drag.current?.moved) { setPlaying(false); focus(i); } }} />
                    <span className="cs-tick" style={{ left: it.x, top: up ? AXIS + 20 : AXIS - 38 }}>{it.c.date?.label}</span>
                    <EventCard it={it} bib={bib} up={up} active={sel === i}
                      onOpen={() => { if (!drag.current?.moved) { setPlaying(false); focus(i); } }} />
                  </div>);
              })}
            </div>
          </div>
          {playing && sel !== null && <div className="cs-progress" key={sel} />}
        </div>

        <div className="cs-minimap mt-3" aria-hidden="true"
          onPointerDown={(e) => {
            const r = e.currentTarget.getBoundingClientRect(), el = scroller.current;
            if (el) el.scrollTo({ left: ((e.clientX - r.left) / r.width) * width - el.clientWidth / 2, behavior: "smooth" });
          }}>
          {items.map((it) => <span key={it.c.id} className="cs-mini-dot" style={{ left: `${(it.x / width) * 100}%`, background: colorOf(it.c.category) }} />)}
          <span className="cs-mini-view" style={{ left: `${view.left * 100}%`, width: `${view.w * 100}%` }} />
        </div>
        <p className="ui muted mt-2 text-xs">
          Escala elástica: los periodos sin hechos se comprimen. <span className="cs-halo-key" /> El halo sobre el eje es el margen real de cada datación.
          {" "}Pasa el ratón para ver el dato, haz clic para abrir sus fuentes.
        </p>
      </>)}

      {current && !extra && (
        <Lens item={current} bib={bib} index={sel!} total={items.length}
          onPrev={() => focus(sel! - 1)} onNext={() => focus(sel! + 1)} onClose={() => { setSel(null); setPlaying(false); }} />)}
      {extra && (
        <Lens item={{ c: extra, title: extra.subject || extra.statement.slice(0, 70), start: 0, end: 0, x: 0, x2: 0, lane: 0, sources: 0 }}
          bib={bib} index={0} total={1} onPrev={() => null} onNext={() => null} onClose={() => setExtra(null)} />)}

      {undated.length > 0 && (
        <div className="mt-8">
          <h3 className="text-lg">Contexto sin fecha</h3>
          <div className="ui mt-3 flex flex-wrap justify-center gap-2">
            {undated.map((c) => (
              <button key={c.id} className="cs-filter" onClick={() => { setSel(null); setExtra(c); }} title={c.statement}>
                <span className="cs-dot" style={{ background: colorOf(c.category) }} />{(c.subject || c.statement).slice(0, 60)}
              </button>))}
          </div>
        </div>)}
    </div>
  );
}
