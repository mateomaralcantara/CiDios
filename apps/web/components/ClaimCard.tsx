"use client";
import Link from "next/link";
import { useState } from "react";
import { CATEGORY_STYLE, STANCE_LABEL, type ClaimRow } from "@/lib/types";

export function CategoryChip({ category, label }: { category: string; label: string }) {
  return <span className={`chip ${CATEGORY_STYLE[category] ?? ""}`}>{label}</span>;
}

export function ClaimCard({ c }: { c: ClaimRow }) {
  const [open, setOpen] = useState(false);
  return (
    <article className="card p-4" data-testid="claim-card">
      <div className="ui mb-2 flex flex-wrap items-center gap-2 text-xs">
        <CategoryChip category={c.category} label={c.category_label} />
        {c.date_label && <span className="chip bg-stone-100 dark:bg-stone-800">{c.date_label} · {c.date_precision_label}</span>}
        <span className="muted">{c.discipline}</span>
        {c.review_status !== "reviewed" && <span className="chip border border-dashed">pendiente de revisión experta</span>}
      </div>
      {c.subject_name && <h3 className="text-lg font-semibold">{c.subject_name}</h3>}
      <p className="mt-1">{c.statement}</p>
      {(c.consensus_note || c.insufficient_evidence_note) && (
        <p className="ui muted mt-2 text-sm">
          {c.consensus_note && <><strong>Consenso:</strong> {c.consensus_note} </>}
          {c.insufficient_evidence_note && <><strong>Límites:</strong> {c.insufficient_evidence_note}</>}
        </p>
      )}
      <button className="ui mt-3 text-sm underline" onClick={() => setOpen(!open)} aria-expanded={open}>
        {open ? "Ocultar" : "Ver"} evidencias ({c.evidence.length}) y perspectivas ({c.perspectives.length})
      </button>
      {open && (
        <div className="mt-3 space-y-2">
          {c.evidence.map((e) => (
            <blockquote key={e.id} className="border-l-4 pl-3 text-sm" style={{ borderColor: e.stance === "challenges" ? "#e11d48" : "var(--accent)" }}>
              <span className="ui chip mr-2 bg-stone-100 dark:bg-stone-800">{STANCE_LABEL[e.stance]}</span>
              “{e.exact_fragment}”
              <div className="ui muted mt-1 text-xs">
                <Link className="underline" href={`/biblioteca/${e.document_id}`}>{e.document_title}</Link> · {e.locator}
                {e.reference_title && <> · fuente citada: {e.reference_authors?.join(", ")}, <em>{e.reference_title}</em> ({e.reference_year ?? "s. f."})</>}
              </div>
            </blockquote>
          ))}
          {c.perspectives.map((p) => (
            <div key={p.label} className="ui rounded-lg border p-2 text-sm" style={{ borderColor: "var(--line)" }}>
              <strong>{p.label}</strong> <span className="muted">({p.tradition}; {p.held_by})</span>: {p.summary}
            </div>
          ))}
        </div>
      )}
    </article>
  );
}
