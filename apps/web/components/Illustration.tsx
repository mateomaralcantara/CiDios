// Ilustraciones vectoriales esquemáticas originales. Representan el tipo de soporte, no el manuscrito real.
import type { Illustration as Ill } from "@/lib/types";

export function IllustrationSvg({ kind, title, size = 96 }: { kind: string; title: string; size?: number }) {
  const s = { stroke: "currentColor", fill: "none", strokeWidth: 2 } as const;
  const shapes: Record<string, React.ReactNode> = {
    scroll: (<>
      <rect x="22" y="22" width="56" height="56" rx="4" {...s} />
      <ellipse cx="22" cy="50" rx="7" ry="30" {...s} /><ellipse cx="78" cy="50" rx="7" ry="30" {...s} />
      {[34, 42, 50, 58, 66].map((y) => <line key={y} x1="32" x2="68" y1={y} y2={y} {...s} strokeWidth={1} />)}
    </>),
    codex: (<>
      <path d="M50 26 C38 20 24 20 14 24 V78 C24 74 38 74 50 80 Z" {...s} />
      <path d="M50 26 C62 20 76 20 86 24 V78 C76 74 62 74 50 80 Z" {...s} />
      {[36, 44, 52, 60].map((y) => <g key={y}><line x1="20" x2="44" y1={y} y2={y + 1} {...s} strokeWidth={1} /><line x1="56" x2="80" y1={y + 1} y2={y} {...s} strokeWidth={1} /></g>)}
    </>),
    papyrus: (<>
      <path d="M26 20 L72 18 L80 40 L74 58 L78 80 L30 82 L22 62 L28 44 Z" {...s} />
      {[32, 40, 48, 56, 64].map((y) => <line key={y} x1="32" x2="70" y1={y} y2={y} {...s} strokeWidth={1} strokeDasharray="4 3" />)}
    </>),
    amulet: (<>
      <rect x="38" y="16" width="24" height="68" rx="12" {...s} />
      {[28, 36, 44, 52, 60, 68].map((y) => <line key={y} x1="42" x2="58" y1={y} y2={y} {...s} strokeWidth={1} />)}
      <circle cx="50" cy="12" r="4" {...s} />
    </>),
    printed_book: (<>
      <rect x="20" y="18" width="60" height="64" rx="3" {...s} />
      <rect x="28" y="26" width="44" height="18" {...s} strokeWidth={1} />
      {[52, 58, 64, 70].map((y) => <g key={y}><line x1="28" x2="48" y1={y} y2={y} {...s} strokeWidth={1} /><line x1="52" x2="72" y1={y} y2={y} {...s} strokeWidth={1} /></g>)}
    </>),
    critical_edition: (<>
      <rect x="20" y="16" width="60" height="68" rx="3" {...s} />
      {[26, 32, 38, 44, 50].map((y) => <line key={y} x1="28" x2="72" y1={y} y2={y} {...s} strokeWidth={1} />)}
      <line x1="28" x2="72" y1="58" y2="58" {...s} />
      {[64, 68, 72, 76].map((y) => <line key={y} x1="28" x2="66" y1={y} y2={y} {...s} strokeWidth={0.7} />)}
    </>),
  };
  return (
    <svg viewBox="0 0 100 100" width={size} height={size} role="img" aria-label={title} className="accent shrink-0">
      <title>{title}</title>
      {shapes[kind] ?? shapes.codex}
    </svg>
  );
}

export function IllustrationFigure({ ill }: { ill: Ill }) {
  return (
    <figure className="flex flex-col items-center gap-2">
      <IllustrationSvg kind={ill.kind} title={ill.alt} />
      <figcaption className="ui muted max-w-md text-[11px] leading-snug">
        <strong>Procedencia:</strong> {ill.provenance.creator} · {ill.provenance.license}
        <br />{ill.provenance.notice}
      </figcaption>
    </figure>
  );
}
