-- =====================================================================
-- CIENCIA DE DIOS — Núcleo de datos (fase 1)
-- 22 tablas del núcleo mínimo (de las 76 diseñadas en docs/DATA-MODEL.md)
-- Compatible con Supabase: usa auth.uid(), roles anon/authenticated/service_role.
-- =====================================================================

create extension if not exists vector;
create extension if not exists pg_trgm;
create extension if not exists unaccent;
create extension if not exists pgcrypto;

-- ---------------------------------------------------------------------
-- Tipos enumerados
-- ---------------------------------------------------------------------
create type public.app_role as enum ('owner', 'editor', 'user');
create type public.visibility as enum ('public', 'private');
create type public.review_status as enum ('draft', 'pending_review', 'reviewed', 'rejected');

-- Las 10 categorías epistémicas obligatorias (sección 1 del mandato).
create type public.epistemic_category as enum (
  'empirical_fact',             -- 1. Hecho empírico comprobable
  'historical_document',        -- 2. Documento / testimonio histórico
  'scholarly_consensus',        -- 3. Consenso científico o académico
  'scientific_hypothesis',      -- 4. Hipótesis científica
  'philosophical_argument',     -- 5. Argumento filosófico
  'theological_interpretation', -- 6. Interpretación teológica
  'religious_belief',           -- 7. Creencia / doctrina religiosa
  'contested',                  -- 8. Afirmación controvertida
  'uncorroborated',             -- 9. Afirmación sin corroboración
  'open_question'               -- 10. Fenómeno cuyo análisis permanece abierto
);

create type public.date_precision as enum (
  'exact_day', 'exact_year', 'approximate_year', 'range', 'decade', 'century', 'disputed', 'unknown'
);

create type public.evidence_stance as enum ('supports', 'challenges', 'contextualizes', 'qualifies');

create type public.entity_kind as enum (
  'person', 'place', 'manuscript', 'edition', 'event', 'concept', 'tradition',
  'institution', 'theory', 'hypothesis', 'artifact', 'period'
);

create type public.run_state as enum (
  'CREATED', 'AUTHORIZED', 'PLANNED', 'ACQUIRING', 'ANALYZING', 'CROSS_EXAMINING',
  'VERIFYING', 'PACKAGING', 'RENDERING', 'QA', 'READY', 'PUBLISHED',
  'FAILED', 'CANCELLED', 'PAUSED', 'AWAITING_APPROVAL', 'LICENSE_BLOCKED',
  'PARTIAL', 'BUDGET_EXHAUSTED'
);

create type public.task_status as enum (
  'pending', 'queued', 'running', 'succeeded', 'failed', 'skipped', 'cancelled', 'blocked'
);

-- =====================================================================
-- DOMINIO 1 — Identidad y autorización (2 de 7)
-- =====================================================================
create table public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  display_name text not null default '',
  preferred_language text not null default 'es',
  academic_level text not null default 'general',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- Los roles viven en una tabla separada para impedir la autoescalada de privilegios.
create table public.user_roles (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role public.app_role not null default 'user',
  granted_by uuid references auth.users(id),
  granted_at timestamptz not null default now()
);

-- =====================================================================
-- DOMINIO 2 — Fuentes documentales (4 de 10)
-- =====================================================================
create table public.licenses (
  code text primary key,                      -- p. ej. 'CC-BY-4.0', 'PUBLIC-DOMAIN', 'PROJECT-EDITORIAL'
  name text not null,
  url text,
  allows_display boolean not null default true,
  allows_excerpt boolean not null default true,
  allows_full_text boolean not null default false,
  allows_derivatives boolean not null default false,
  requires_attribution boolean not null default true,
  notes text not null default ''
);

create table public.bibliographic_references (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  ref_type text not null check (ref_type in ('book','article','chapter','website','dataset','catalog_record','edition','other')),
  authors text[] not null default '{}',
  title text not null,
  container_title text,                        -- revista, serie o sitio
  publisher text,
  year int,
  edition text,
  language text,
  identifiers jsonb not null default '{}',     -- {"isbn": "...", "doi": "...", "url": "..."}
  -- Estado de comprobación del identificador externo. 'unverified_offline' = no se pudo resolver en línea.
  identifier_check text not null default 'unverified_offline'
    check (identifier_check in ('unverified_offline','resolved','failed','not_applicable')),
  checked_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.documents (
  id uuid primary key default gen_random_uuid(),
  slug text unique,
  title text not null,
  doc_kind text not null check (doc_kind in ('editorial_note','primary_text','secondary_text','catalog_record','user_upload','connector_record')),
  authors text[] not null default '{}',
  institution text,
  published_date text,                          -- texto libre: las fechas documentales no siempre son ISO
  language text not null default 'es',
  edition text,
  identifier text,
  license_code text not null references public.licenses(code),
  rights_statement text not null default '',
  provenance jsonb not null default '{}',       -- origen, conector, quién lo aportó, cadena de custodia
  consulted_at timestamptz,
  content_sha256 text not null,
  body text not null,
  owner_id uuid references auth.users(id) on delete set null,
  visibility public.visibility not null default 'private',
  review_status public.review_status not null default 'draft',
  cites uuid[] not null default '{}',           -- referencias bibliográficas que la nota documenta
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (content_sha256)
);

create table public.document_chunks (
  id uuid primary key default gen_random_uuid(),
  document_id uuid not null references public.documents(id) on delete cascade,
  ordinal int not null,
  locator text not null default '',             -- sección, página o versículo
  content text not null,
  content_tsv tsvector,
  embedding vector(384),
  embedding_model text not null default '',
  injection_risk boolean not null default false,
  injection_signals text[] not null default '{}',
  created_at timestamptz not null default now(),
  unique (document_id, ordinal)
);

-- =====================================================================
-- DOMINIO 3 — Ontología y evidencias (6 de 10)
-- =====================================================================
create table public.topics (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  title text not null,
  summary text not null default '',
  sort_order int not null default 0,
  content_status text not null default 'empty' check (content_status in ('empty','in_progress','seeded','reviewed')),
  open_questions text[] not null default '{}',
  created_at timestamptz not null default now()
);

create table public.entities (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  kind public.entity_kind not null,
  name text not null,
  description text not null default '',
  attributes jsonb not null default '{}',       -- coordenadas, signaturas, colecciones, etc.
  topic_id uuid references public.topics(id) on delete set null,
  created_at timestamptz not null default now()
);

create table public.entity_relations (
  id uuid primary key default gen_random_uuid(),
  subject_id uuid not null references public.entities(id) on delete cascade,
  predicate text not null check (predicate in (
    'located_in','held_by','found_at','produced_at','copy_of','edition_of','based_on',
    'translated_from','authored_by','part_of','precedes','influenced','contradicts','supports','related_to'
  )),
  object_id uuid not null references public.entities(id) on delete cascade,
  evidence_claim_id uuid,
  created_at timestamptz not null default now(),
  unique (subject_id, predicate, object_id)
);

create table public.claims (
  id uuid primary key default gen_random_uuid(),
  slug text unique not null,
  topic_id uuid references public.topics(id) on delete set null,
  statement text not null,                      -- qué se afirma
  asserted_by text not null default '',         -- quién lo afirma
  discipline text not null,                     -- qué disciplina permite evaluarlo
  category public.epistemic_category not null,
  is_event boolean not null default false,
  date_start int,                               -- año astronómico: -600 = 601 a. e. c.
  date_end int,
  date_precision public.date_precision not null default 'unknown',
  date_label text not null default '',
  place_entity_id uuid references public.entities(id) on delete set null,
  subject_entity_id uuid references public.entities(id) on delete set null,
  consensus_note text not null default '',      -- qué consenso académico existe
  insufficient_evidence_note text not null default '',
  future_research_note text not null default '',-- qué investigaciones podrían modificarla
  review_status public.review_status not null default 'draft',
  visibility public.visibility not null default 'public',
  content_sha256 text not null,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  check (date_end is null or date_start is null or date_end >= date_start)
);

alter table public.entity_relations
  add constraint entity_relations_claim_fk foreign key (evidence_claim_id) references public.claims(id) on delete set null;

create table public.evidence_links (
  id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references public.claims(id) on delete cascade,
  chunk_id uuid not null references public.document_chunks(id) on delete restrict,
  reference_id uuid references public.bibliographic_references(id) on delete set null,
  stance public.evidence_stance not null,
  exact_fragment text not null,                 -- debe aparecer literalmente en el fragmento
  locator text not null default '',             -- página, sección, versículo
  note text not null default '',
  verification_status text not null default 'unverified'
    check (verification_status in ('unverified','fragment_verified','fragment_mismatch','reference_missing')),
  verified_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.perspectives (
  id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references public.claims(id) on delete cascade,
  label text not null,                          -- p. ej. 'Datación temprana (paleográfica tradicional)'
  tradition text not null,                      -- 'académica', 'judía', 'cristiana', 'escéptica', ...
  summary text not null,
  held_by text not null default '',
  evidence_link_ids uuid[] not null default '{}',
  created_at timestamptz not null default now()
);

-- =====================================================================
-- DOMINIO 4 — Investigación (1 de 8)
-- =====================================================================
create table public.investigations (
  id uuid primary key default gen_random_uuid(),
  owner_id uuid not null references auth.users(id) on delete cascade,
  prompt text not null,
  prompt_sha256 text not null,                    -- detección de consultas redundantes
  preferences jsonb not null default '{}',
  intent jsonb not null default '{}',
  status text not null default 'open' check (status in ('open','running','ready','published','archived','failed')),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- =====================================================================
-- DOMINIO 5 — HARNESS (5 de 12)
-- =====================================================================
create table public.agent_definitions (
  code text primary key,                        -- 'intent_interpreter', ...
  number int unique not null check (number between 1 and 40),
  family text not null,
  name_es text not null,
  version text not null,
  status text not null check (status in ('operational','registered','disabled')),
  enabled boolean not null default true,
  execution_model text not null,                -- 'deterministic', 'llm', 'hybrid'
  allowed_tools text[] not null default '{}',
  input_contract text not null,
  output_contract text not null,
  rules text[] not null default '{}',
  unit_cost_usd numeric(12,6) not null default 0,
  max_cost_per_run_usd numeric(12,6) not null default 1,
  fallback text not null default '',
  updated_at timestamptz not null default now()
);

create table public.harness_runs (
  id uuid primary key default gen_random_uuid(),
  investigation_id uuid not null references public.investigations(id) on delete cascade,
  owner_id uuid not null references auth.users(id) on delete cascade,
  state public.run_state not null default 'CREATED',
  previous_state public.run_state,
  budget_usd numeric(12,6) not null default 1,
  spent_usd numeric(12,6) not null default 0,
  estimated_usd numeric(12,6) not null default 0,
  requires_approval boolean not null default false,
  approved_by uuid references auth.users(id),
  approved_at timestamptz,
  pause_requested boolean not null default false,
  cancel_requested boolean not null default false,
  queued boolean not null default false,          -- cola de trabajo respaldada por Postgres
  worker_lease_until timestamptz,                 -- arrendamiento del worker (for update skip locked)
  plan jsonb not null default '{}',
  result jsonb not null default '{}',
  error text,
  contract_version text not null default '1.0.0',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  finished_at timestamptz
);

create table public.harness_tasks (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.harness_runs(id) on delete cascade,
  task_key text not null,
  agent_code text not null references public.agent_definitions(code),
  phase public.run_state not null,
  depends_on text[] not null default '{}',
  status public.task_status not null default 'pending',
  attempts int not null default 0,
  max_attempts int not null default 2,
  budget_usd numeric(12,6) not null default 0,
  cost_usd numeric(12,6) not null default 0,
  allowed_tools text[] not null default '{}',
  agent_version text not null default '',
  input jsonb not null default '{}',
  output jsonb not null default '{}',
  completion_criteria text not null default '',
  error text,
  started_at timestamptz,
  finished_at timestamptz,
  created_at timestamptz not null default now(),
  unique (run_id, task_key)
);

create table public.harness_events (
  id bigserial primary key,
  run_id uuid not null references public.harness_runs(id) on delete cascade,
  task_key text,
  level text not null default 'info' check (level in ('debug','info','warning','error','audit')),
  event_type text not null,
  message text not null,
  data jsonb not null default '{}',
  created_at timestamptz not null default now()
);

create table public.harness_checkpoints (
  id uuid primary key default gen_random_uuid(),
  run_id uuid not null references public.harness_runs(id) on delete cascade,
  task_key text not null,
  state public.run_state not null,
  output_sha256 text not null,
  snapshot jsonb not null,
  created_at timestamptz not null default now(),
  unique (run_id, task_key)
);

-- =====================================================================
-- DOMINIO 6 — Experiencias (1 de 11)
-- =====================================================================
create table public.experiences (
  id uuid primary key default gen_random_uuid(),
  run_id uuid references public.harness_runs(id) on delete set null,
  owner_id uuid not null references auth.users(id) on delete cascade,
  modality text not null check (modality in (
    'article','comparison_matrix','timeline','gamified_timeline','atlas','knowledge_graph','debate',
    'infographic','scientific_chart','interactive_lesson','conceptual_simulation','illustrated_narrative',
    'podcast','mini_documentary','explorable_3d','research_report'
  )),
  title text not null,
  knowledge_packet jsonb not null,
  knowledge_packet_sha256 text not null,
  experience_spec jsonb not null,
  status text not null default 'draft' check (status in ('draft','ready','published','archived')),
  published_by uuid references auth.users(id),
  published_at timestamptz,
  created_at timestamptz not null default now()
);

-- =====================================================================
-- DOMINIO 8 — Educación (1 de 6)
-- =====================================================================
create table public.learning_progress (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  experience_id uuid not null references public.experiences(id) on delete cascade,
  completed_missions text[] not null default '{}',
  answers jsonb not null default '{}',
  score int not null default 0,
  unlocked_stage int not null default 0,
  updated_at timestamptz not null default now(),
  unique (user_id, experience_id)
);

-- =====================================================================
-- DOMINIO 9 — Operaciones y evaluación (2 de 6)
-- =====================================================================
create table public.budget_policies (
  id uuid primary key default gen_random_uuid(),
  scope text not null check (scope in ('global','user','investigation','agent','provider')),
  scope_ref text not null default '*',
  period text not null check (period in ('per_run','daily','monthly')),
  limit_usd numeric(12,6) not null check (limit_usd >= 0),
  auto_approve_below_usd numeric(12,6) not null default 0.50,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  unique (scope, scope_ref, period)
);

create table public.cost_ledger (
  id bigserial primary key,
  run_id uuid references public.harness_runs(id) on delete set null,
  user_id uuid references auth.users(id) on delete set null,
  agent_code text,
  provider text not null default 'local',
  model text not null default 'deterministic',
  kind text not null check (kind in ('estimate','actual','refund')),
  input_tokens int not null default 0,
  output_tokens int not null default 0,
  amount_usd numeric(12,6) not null default 0,
  cache_hit boolean not null default false,
  note text not null default '',
  created_at timestamptz not null default now()
);

-- =====================================================================
-- Índices
-- =====================================================================
create index on public.document_chunks using gin (content_tsv);
create index on public.document_chunks using hnsw (embedding vector_cosine_ops);
create index on public.document_chunks (document_id);
create index on public.documents using gin (title gin_trgm_ops);
create index on public.claims (topic_id);
create index on public.claims (date_start);
create index on public.evidence_links (claim_id);
create index on public.evidence_links (chunk_id);
create index on public.perspectives (claim_id);
create index on public.harness_runs (owner_id, created_at desc);
create index on public.harness_runs (queued) where queued;
create index on public.investigations (owner_id, prompt_sha256);
create index on public.harness_tasks (run_id, status);
create index on public.harness_events (run_id, id);
create index on public.cost_ledger (run_id);
create index on public.cost_ledger (user_id, created_at);
create index on public.experiences (owner_id);
create index on public.learning_progress (user_id);

-- =====================================================================
-- Búsqueda textual: tsvector en español sin acentos
-- =====================================================================
create text search configuration public.es_unaccent (copy = pg_catalog.spanish);
alter text search configuration public.es_unaccent
  alter mapping for hword, hword_part, word with unaccent, spanish_stem;

create or replace function public.chunks_tsv_trigger() returns trigger
language plpgsql as $$
begin
  new.content_tsv := setweight(to_tsvector('public.es_unaccent', coalesce(new.locator, '')), 'B')
                  || setweight(to_tsvector('public.es_unaccent', coalesce(new.content, '')), 'A');
  return new;
end $$;

create trigger trg_chunks_tsv before insert or update of content, locator on public.document_chunks
  for each row execute function public.chunks_tsv_trigger();

create or replace function public.touch_updated_at() returns trigger
language plpgsql as $$ begin new.updated_at := now(); return new; end $$;

create trigger trg_profiles_touch before update on public.profiles for each row execute function public.touch_updated_at();
create trigger trg_documents_touch before update on public.documents for each row execute function public.touch_updated_at();
create trigger trg_claims_touch before update on public.claims for each row execute function public.touch_updated_at();
create trigger trg_investigations_touch before update on public.investigations for each row execute function public.touch_updated_at();
create trigger trg_runs_touch before update on public.harness_runs for each row execute function public.touch_updated_at();

-- Un documento solo puede citarse si el fragmento exacto aparece en el fragmento indexado.
create or replace function public.evidence_fragment_check() returns trigger
language plpgsql as $$
declare chunk_text text;
begin
  select content into chunk_text from public.document_chunks where id = new.chunk_id;
  if chunk_text is null then
    raise exception 'evidence chunk % does not exist', new.chunk_id;
  end if;
  if position(regexp_replace(new.exact_fragment, '\s+', ' ', 'g') in regexp_replace(chunk_text, '\s+', ' ', 'g')) = 0 then
    raise exception 'exact_fragment does not appear in chunk % (fabricated citation rejected)', new.chunk_id
      using errcode = 'check_violation';
  end if;
  return new;
end $$;

create trigger trg_evidence_fragment before insert or update of exact_fragment, chunk_id on public.evidence_links
  for each row execute function public.evidence_fragment_check();
