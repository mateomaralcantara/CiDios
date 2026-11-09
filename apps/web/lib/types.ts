// Contratos espejo de packages/contracts (KnowledgePacket 1.0.0 / ExperienceSpec 1.0.0).
export type Stance = "supports" | "challenges" | "contextualizes" | "qualifies";

export interface BibRef {
  id: string; slug: string; authors: string[]; title: string; container_title?: string | null;
  publisher?: string | null; year?: number | null; edition?: string | null; identifiers: Record<string, string>;
  identifier_check: string;
}

export interface EvidenceItem {
  id: string; stance: Stance; fragment: string; locator: string;
  document: { id: string; title: string; slug?: string | null; license_code: string; review_status: string; kind: string };
  reference?: BibRef | null; verification: string; verification_notes: string[];
}

export interface Perspective { label: string; tradition: string; summary: string; held_by: string }

export interface PacketClaim {
  id: string; slug: string; statement: string; statement_sha256: string; asserted_by: string; discipline: string;
  category: string; category_label: string; is_event: boolean;
  date?: { start: number | null; end: number | null; precision: string; precision_label: string; label: string } | null;
  place?: { name: string; lat?: number | null; lon?: number | null } | null;
  subject?: string | null; illustration_kind?: string | null; consensus_note: string; insufficient_evidence_note: string;
  future_research_note: string; review_status: string; evidence: EvidenceItem[]; perspectives: Perspective[];
}

export interface KnowledgePacket {
  packet_version: string; run_id: string; question: string; topic: string | null; generated_at: string;
  claims: PacketClaim[]; excluded_claims: { claim_id: string; reason: string }[]; uncertainties: string[];
  limitations: string[]; coverage: { by_era?: Record<string, number>; gaps?: string[] }; sha256: string;
}

export interface Question {
  id: string; claim_id: string; kind: string; prompt: string; options: string[]; correct_index: number; explanation: string;
}
export interface Mission { id: string; title: string; objective: string; questions: Question[]; pass_threshold: number }
export interface Stage {
  id: string; index: number; title: string; range_label: string; intro: string; event_claim_ids: string[]; mission?: Mission | null;
}
export interface Illustration {
  kind: string; alt: string;
  provenance: { creator: string; kind: string; license: string; is_reconstruction: boolean; notice: string; source_url?: string | null };
}
export interface TimelineEvent {
  claim_id: string; title: string; sort_key: number; date_label: string; precision: string; stage_id: string;
  narration: string; illustration: Illustration; place_name?: string | null;
}
export interface MapSpec {
  kind: "schematic"; notice: string; bounds: { min_lat: number; max_lat: number; min_lon: number; max_lon: number };
  points: { name: string; lat: number; lon: number; claim_ids: string[] }[];
}
export interface ExperienceSpec {
  spec_version: string; modality: "article" | "comparison_matrix" | "timeline" | "gamified_timeline"; title: string;
  language: string; packet_sha256: string; gamified: boolean; academic_mode_available: boolean;
  narration: { engine?: string; paid?: boolean; optional?: boolean };
  stages: Stage[]; events: TimelineEvent[]; map?: MapSpec | null;
  sections: { heading: string; intro: string; claim_ids: string[] }[]; notices: string[];
}

export interface Experience {
  id: string; run_id: string; owner_id: string; modality: string; title: string; status: string;
  knowledge_packet: KnowledgePacket; knowledge_packet_sha256: string; experience_spec: ExperienceSpec;
  created_at: string; published_at: string | null;
}

export interface Progress { completed_missions: string[]; answers: Record<string, Record<string, number>>; score: number; unlocked_stage: number }

export interface ClaimRow {
  id: string; slug: string; statement: string; asserted_by: string; discipline: string; category: string; category_label: string;
  is_event: boolean; date_start: number | null; date_end: number | null; date_precision: string; date_precision_label: string;
  date_label: string; consensus_note: string; insufficient_evidence_note: string; future_research_note: string;
  review_status: string; place_name: string | null; subject_name: string | null;
  evidence: {
    id: string; stance: Stance; exact_fragment: string; locator: string; document_id: string; document_title: string;
    license_code: string; verification_status: string; reference_slug: string | null; reference_title: string | null;
    reference_authors: string[] | null; reference_year: number | null;
  }[];
  perspectives: Perspective[];
}

export const STANCE_LABEL: Record<Stance, string> = {
  supports: "Respalda", challenges: "Cuestiona", contextualizes: "Contextualiza", qualifies: "Matiza",
};

export const CATEGORY_STYLE: Record<string, string> = {
  empirical_fact: "bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200",
  historical_document: "bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200",
  scholarly_consensus: "bg-indigo-100 text-indigo-900 dark:bg-indigo-900/40 dark:text-indigo-200",
  scientific_hypothesis: "bg-violet-100 text-violet-900 dark:bg-violet-900/40 dark:text-violet-200",
  philosophical_argument: "bg-fuchsia-100 text-fuchsia-900 dark:bg-fuchsia-900/40 dark:text-fuchsia-200",
  theological_interpretation: "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200",
  religious_belief: "bg-orange-100 text-orange-900 dark:bg-orange-900/40 dark:text-orange-200",
  contested: "bg-rose-100 text-rose-900 dark:bg-rose-900/40 dark:text-rose-200",
  uncorroborated: "bg-stone-200 text-stone-900 dark:bg-stone-700 dark:text-stone-100",
  open_question: "bg-yellow-100 text-yellow-900 dark:bg-yellow-900/40 dark:text-yellow-200",
};
