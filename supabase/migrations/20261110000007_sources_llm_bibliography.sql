-- =====================================================================
-- Tres dimensiones de búsqueda + extracción con LLM + HARNESS de bibliografía
-- =====================================================================

-- Nivel de procedencia de cada documento y de cada referencia
alter table public.documents
  add column if not exists source_tier text not null default 'editorial'
    check (source_tier in ('expert_peer_reviewed','peer_reviewed','published','preprint','editorial','user')),
  add column if not exists doi text;
create unique index if not exists documents_doi_unique on public.documents (lower(doi)) where doi is not null;
update public.documents set source_tier = 'user' where doc_kind = 'user_upload';

alter table public.bibliographic_references
  add column if not exists tier text not null default 'published'
    check (tier in ('expert_peer_reviewed','peer_reviewed','published','preprint','editorial','user')),
  add column if not exists doi text,
  add column if not exists url text,
  add column if not exists openalex_id text,
  add column if not exists venue_type text,
  add column if not exists cited_by_count int,
  add column if not exists is_retracted boolean not null default false,
  add column if not exists retraction_checked_at timestamptz,
  add column if not exists source_connector text;
create unique index if not exists refs_doi_unique on public.bibliographic_references (lower(doi)) where doi is not null;

-- Origen de cada afirmación: curada por el equipo o propuesta por un modelo (pendiente de revisión)
alter table public.claims
  add column if not exists origin text not null default 'curated' check (origin in ('curated','llm_extracted')),
  add column if not exists generated_by jsonb not null default '{}',
  add column if not exists run_id uuid references public.harness_runs(id) on delete set null;
create index if not exists claims_run_idx on public.claims (run_id);

comment on column public.documents.source_tier is 'Procedencia: expert_peer_reviewed (dimensión 2), peer_reviewed / published / preprint (dimensión 1), editorial, user.';
comment on column public.claims.origin is 'curated = redactada y citada por el equipo; llm_extracted = propuesta por un modelo a partir de fragmentos verificados literalmente, pendiente de revisión.';
