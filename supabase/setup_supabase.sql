-- =====================================================================
-- CIENCIA Y DIOS — creación completa de las tablas en Supabase
-- Generado con «python -m cdd.migrate --bundle». No editar a mano.
-- Pegar entero en Supabase → SQL Editor → New query → Run.
-- Todo se ejecuta en una sola transacción: si algo falla, no se crea nada.
-- =====================================================================
begin;

do $$ begin
  if to_regclass('public.claims') is not null then
    raise exception 'Las tablas de CIENCIA Y DIOS ya existen en esta base. Usa «python -m cdd.migrate» para aplicar solo lo pendiente.';
  end if;
end $$;

-- ######## 20261109000001_core ########
-- =====================================================================
-- CIENCIA Y DIOS — Núcleo de datos (fase 1)
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

-- ######## 20261109000002_rls ########
-- =====================================================================
-- CIENCIA Y DIOS — Seguridad a nivel de fila (RLS)
-- Toda tabla expuesta tiene RLS habilitado y políticas explícitas.
-- Roles: visitante (anon), usuario (authenticated + role user), editor, propietario (owner).
-- =====================================================================

-- Funciones auxiliares (security definer, search_path fijo para evitar secuestro)
create or replace function public.current_app_role() returns public.app_role
language sql stable security definer set search_path = public, pg_temp as $$
  select coalesce((select role from public.user_roles where user_id = auth.uid()), 'user'::public.app_role)
$$;

create or replace function public.is_owner() returns boolean
language sql stable security definer set search_path = public, pg_temp as $$
  select auth.uid() is not null and public.current_app_role() = 'owner'
$$;

create or replace function public.is_staff() returns boolean
language sql stable security definer set search_path = public, pg_temp as $$
  select auth.uid() is not null and public.current_app_role() in ('owner','editor')
$$;

revoke all on function public.current_app_role() from public;
revoke all on function public.is_owner() from public;
revoke all on function public.is_staff() from public;
grant execute on function public.current_app_role() to anon, authenticated, service_role;
grant execute on function public.is_owner() to anon, authenticated, service_role;
grant execute on function public.is_staff() to anon, authenticated, service_role;

do $$
declare t text;
begin
  foreach t in array array[
    'profiles','user_roles','licenses','bibliographic_references','documents','document_chunks',
    'topics','entities','entity_relations','claims','evidence_links','perspectives',
    'investigations','agent_definitions','harness_runs','harness_tasks','harness_events',
    'harness_checkpoints','experiences','learning_progress','budget_policies','cost_ledger'
  ] loop
    execute format('alter table public.%I enable row level security', t);
    execute format('alter table public.%I force row level security', t);
    execute format('revoke all on public.%I from anon, authenticated', t);
  end loop;
end $$;

grant usage on schema public to anon, authenticated;

-- ---------------- profiles ----------------
grant select, insert on public.profiles to authenticated;
grant update (display_name, preferred_language, academic_level) on public.profiles to authenticated;
create policy profiles_select on public.profiles for select to authenticated
  using (id = auth.uid() or public.is_staff());
create policy profiles_insert on public.profiles for insert to authenticated
  with check (id = auth.uid());
create policy profiles_update on public.profiles for update to authenticated
  using (id = auth.uid()) with check (id = auth.uid());

-- ---------------- user_roles (solo el propietario asigna roles) ----------------
grant select, insert, update, delete on public.user_roles to authenticated;
create policy roles_select on public.user_roles for select to authenticated
  using (user_id = auth.uid() or public.is_owner());
create policy roles_write on public.user_roles for all to authenticated
  using (public.is_owner()) with check (public.is_owner());

-- ---------------- catálogo público de lectura ----------------
grant select on public.licenses, public.bibliographic_references, public.topics, public.entities,
  public.entity_relations to anon, authenticated;
grant insert, update, delete on public.licenses, public.bibliographic_references, public.topics,
  public.entities, public.entity_relations to authenticated;

create policy licenses_read on public.licenses for select to anon, authenticated using (true);
create policy licenses_write on public.licenses for all to authenticated using (public.is_staff()) with check (public.is_staff());
create policy refs_read on public.bibliographic_references for select to anon, authenticated using (true);
create policy refs_write on public.bibliographic_references for all to authenticated using (public.is_staff()) with check (public.is_staff());
create policy topics_read on public.topics for select to anon, authenticated using (true);
create policy topics_write on public.topics for all to authenticated using (public.is_staff()) with check (public.is_staff());
create policy entities_read on public.entities for select to anon, authenticated using (true);
create policy entities_write on public.entities for all to authenticated using (public.is_staff()) with check (public.is_staff());
create policy relations_read on public.entity_relations for select to anon, authenticated using (true);
create policy relations_write on public.entity_relations for all to authenticated using (public.is_staff()) with check (public.is_staff());

-- ---------------- documents ----------------
grant select on public.documents to anon, authenticated;
grant insert, update, delete on public.documents to authenticated;
create policy documents_read_public on public.documents for select to anon, authenticated
  using (visibility = 'public' and review_status <> 'rejected');
create policy documents_read_own on public.documents for select to authenticated
  using (owner_id = auth.uid() or public.is_staff());
-- Un usuario regular solo puede aportar documentos privados propios (requieren revisión para publicarse).
create policy documents_insert on public.documents for insert to authenticated
  with check (public.is_staff() or (owner_id = auth.uid() and visibility = 'private' and doc_kind = 'user_upload'));
create policy documents_update on public.documents for update to authenticated
  using (public.is_staff() or owner_id = auth.uid())
  with check (public.is_staff() or (owner_id = auth.uid() and visibility = 'private'));
create policy documents_delete on public.documents for delete to authenticated
  using (public.is_staff() or owner_id = auth.uid());

-- ---------------- document_chunks (heredan la visibilidad del documento) ----------------
grant select on public.document_chunks to anon, authenticated;
grant insert, update, delete on public.document_chunks to authenticated;
create policy chunks_read on public.document_chunks for select to anon, authenticated
  using (exists (select 1 from public.documents d where d.id = document_id));  -- RLS de documents se aplica dentro
create policy chunks_write on public.document_chunks for all to authenticated
  using (exists (select 1 from public.documents d where d.id = document_id and (public.is_staff() or d.owner_id = auth.uid())))
  with check (exists (select 1 from public.documents d where d.id = document_id and (public.is_staff() or d.owner_id = auth.uid())));

-- ---------------- claims / evidencias / perspectivas ----------------
grant select on public.claims, public.evidence_links, public.perspectives to anon, authenticated;
grant insert, update, delete on public.claims, public.evidence_links, public.perspectives to authenticated;
create policy claims_read on public.claims for select to anon, authenticated
  using ((visibility = 'public' and review_status <> 'rejected') or created_by = auth.uid() or public.is_staff());
create policy claims_write on public.claims for all to authenticated using (public.is_staff()) with check (public.is_staff());
create policy evidence_read on public.evidence_links for select to anon, authenticated
  using (exists (select 1 from public.claims c where c.id = claim_id));
create policy evidence_write on public.evidence_links for all to authenticated using (public.is_staff()) with check (public.is_staff());
create policy perspectives_read on public.perspectives for select to anon, authenticated
  using (exists (select 1 from public.claims c where c.id = claim_id));
create policy perspectives_write on public.perspectives for all to authenticated using (public.is_staff()) with check (public.is_staff());

-- ---------------- investigaciones ----------------
grant select, insert, update on public.investigations to authenticated;
create policy inv_select on public.investigations for select to authenticated
  using (owner_id = auth.uid() or public.is_owner());
create policy inv_insert on public.investigations for insert to authenticated
  with check (owner_id = auth.uid());
create policy inv_update on public.investigations for update to authenticated
  using (owner_id = auth.uid() or public.is_owner()) with check (owner_id = auth.uid() or public.is_owner());

-- ---------------- agentes (lectura autenticada, escritura propietario) ----------------
grant select, update on public.agent_definitions to authenticated;
create policy agents_read on public.agent_definitions for select to authenticated using (true);
create policy agents_write on public.agent_definitions for update to authenticated
  using (public.is_owner()) with check (public.is_owner());

-- ---------------- HARNESS (lectura del dueño de la ejecución y del propietario; escritura solo backend) ----------------
grant select on public.harness_runs, public.harness_tasks, public.harness_events, public.harness_checkpoints to authenticated;
create policy runs_read on public.harness_runs for select to authenticated
  using (owner_id = auth.uid() or public.is_owner());
create policy tasks_read on public.harness_tasks for select to authenticated
  using (exists (select 1 from public.harness_runs r where r.id = run_id));
create policy events_read on public.harness_events for select to authenticated
  using (exists (select 1 from public.harness_runs r where r.id = run_id));
create policy checkpoints_read on public.harness_checkpoints for select to authenticated
  using (exists (select 1 from public.harness_runs r where r.id = run_id));

-- ---------------- experiencias ----------------
grant select on public.experiences to anon, authenticated;
create policy experiences_read_published on public.experiences for select to anon, authenticated
  using (status = 'published');
create policy experiences_read_own on public.experiences for select to authenticated
  using (owner_id = auth.uid() or public.is_staff());

-- ---------------- progreso educativo (estrictamente personal) ----------------
grant select, insert, update on public.learning_progress to authenticated;
create policy progress_select on public.learning_progress for select to authenticated
  using (user_id = auth.uid() or public.is_owner());
create policy progress_insert on public.learning_progress for insert to authenticated
  with check (user_id = auth.uid() and exists (select 1 from public.experiences e where e.id = experience_id));
create policy progress_update on public.learning_progress for update to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

-- ---------------- presupuestos y gastos ----------------
grant select, insert, update, delete on public.budget_policies to authenticated;
grant select on public.cost_ledger to authenticated;
create policy budgets_owner on public.budget_policies for all to authenticated
  using (public.is_owner()) with check (public.is_owner());
create policy ledger_read on public.cost_ledger for select to authenticated
  using (user_id = auth.uid() or public.is_owner());

-- Secuencias necesarias para inserciones del cliente
grant usage on all sequences in schema public to authenticated;

-- ######## 20261109000003_search ########
-- =====================================================================
-- Búsqueda híbrida (textual + vectorial) con fusión por rango recíproco (RRF).
-- security invoker: respeta RLS del usuario que consulta.
-- =====================================================================
create or replace function public.hybrid_search(
  query_text text,
  query_embedding vector(384),
  match_count int default 10,
  mode text default 'hybrid'          -- 'text' | 'semantic' | 'hybrid'
) returns table (
  chunk_id uuid, document_id uuid, document_title text, locator text, content text,
  text_rank real, semantic_score real, score real, injection_risk boolean
)
language sql stable security invoker set search_path = public, pg_temp as $$
  -- Consulta en lenguaje natural: los términos se combinan con OR para no exigir que todos aparezcan;
  -- ts_rank_cd premia los fragmentos que contienen más términos. Las frases entre comillas se conservan.
  with q as (
    select coalesce(nullif(replace(websearch_to_tsquery('public.es_unaccent', query_text)::text, ' & ', ' | '), ''), '''''')::tsquery as tsq
  ),
  t as (
    select c.id, ts_rank_cd(c.content_tsv, q.tsq) as r,
           row_number() over (order by ts_rank_cd(c.content_tsv, q.tsq) desc) as rn
    from public.document_chunks c, q
    where mode in ('text','hybrid') and c.content_tsv @@ q.tsq
    order by r desc limit greatest(match_count * 4, 20)
  ),
  s as (
    select c.id, 1 - (c.embedding <=> query_embedding) as sim,
           row_number() over (order by c.embedding <=> query_embedding) as rn
    from public.document_chunks c
    where mode in ('semantic','hybrid') and query_embedding is not null and c.embedding is not null
      and 1 - (c.embedding <=> query_embedding) >= 0.1   -- descarta la cola de ruido del embedder léxico
    order by c.embedding <=> query_embedding limit greatest(match_count * 4, 20)
  ),
  fused as (
    select coalesce(t.id, s.id) as id,
           coalesce(t.r, 0)::real as text_rank,
           coalesce(s.sim, 0)::real as semantic_score,
           (coalesce(1.0 / (60 + t.rn), 0) + coalesce(1.0 / (60 + s.rn), 0))::real as score
    from t full outer join s on t.id = s.id
  )
  select c.id, d.id, d.title, c.locator, c.content, f.text_rank, f.semantic_score, f.score, c.injection_risk
  from fused f
  join public.document_chunks c on c.id = f.id
  join public.documents d on d.id = c.document_id
  order by f.score desc
  limit match_count
$$;

grant execute on function public.hybrid_search(text, vector, int, text) to anon, authenticated;

-- ######## 20261109000004_auth_hooks ########
-- Crea el perfil y el rol 'user' cuando Supabase Auth registra un usuario.
-- El primer propietario se asigna manualmente (ver docs/RUNBOOK.md); nunca desde el cliente.
create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public, pg_temp as $$
begin
  insert into public.profiles (id, display_name)
    values (new.id, coalesce(split_part(new.email, '@', 1), '')) on conflict (id) do nothing;
  insert into public.user_roles (user_id, role) values (new.id, 'user') on conflict (user_id) do nothing;
  return new;
end $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();

-- ######## 20261110000005_supabase_compat ########
-- =====================================================================
-- Compatibilidad con Supabase (donde el rol "postgres" NO es superusuario).
--
-- 1) Sin FORCE ROW LEVEL SECURITY: el dueño de las tablas (postgres, con el que el backend
--    ejecuta los workers del HARNESS) no debe quedar sujeto a sus propias políticas.
--    RLS sigue habilitado y se aplica íntegramente a anon y authenticated (los roles que usan
--    la API REST de Supabase, supabase-js y las transacciones de usuario del backend).
-- 2) hybrid_search incluye el esquema "extensions" en su search_path, porque en Supabase
--    pgvector puede estar instalado ahí.
-- =====================================================================
do $$
declare t text;
begin
  foreach t in array array[
    'profiles','user_roles','licenses','bibliographic_references','documents','document_chunks',
    'topics','entities','entity_relations','claims','evidence_links','perspectives',
    'investigations','agent_definitions','harness_runs','harness_tasks','harness_events',
    'harness_checkpoints','experiences','learning_progress','budget_policies','cost_ledger'
  ] loop
    execute format('alter table public.%I no force row level security', t);
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;

alter function public.hybrid_search(text, vector, int, text) set search_path = public, extensions, pg_temp;

-- 3) Descripciones (visibles en el panel de Supabase, en la API REST y en docs/API-TABLAS.md)
comment on table public.profiles is 'Perfil público de cada usuario de Supabase Auth (nombre, idioma, nivel).';
comment on table public.user_roles is 'Rol de aplicación por usuario (owner, editor, user). Solo el propietario lo modifica.';
comment on table public.licenses is 'Licencias y derechos de uso de los documentos (qué se puede mostrar, citar o derivar).';
comment on table public.bibliographic_references is 'Referencias bibliográficas externas (libros, artículos, sitios) con estado de verificación del identificador.';
comment on table public.documents is 'Documentos de la biblioteca con procedencia, licencia, hash de contenido y estado de revisión.';
comment on table public.document_chunks is 'Fragmentos indexados de cada documento (texto, localizador, tsvector, embedding, riesgo de inyección).';
comment on table public.topics is 'Las 20 áreas de la enciclopedia y sus preguntas abiertas.';
comment on table public.entities is 'Entidades del grafo: personas, lugares, manuscritos, ediciones, conceptos…';
comment on table public.entity_relations is 'Relaciones tipadas entre entidades del grafo de conocimiento.';
comment on table public.claims is 'Afirmaciones con categoría epistémica, disciplina, fechas y su precisión, consenso e incertidumbre.';
comment on table public.evidence_links is 'Evidencias: fragmento literal de una fuente que respalda, cuestiona, matiza o contextualiza una afirmación.';
comment on table public.perspectives is 'Posturas documentadas sobre una afirmación (tradición, quién la sostiene, resumen).';
comment on table public.investigations is 'Investigaciones solicitadas por los usuarios (consulta, preferencias, intención interpretada).';
comment on table public.agent_definitions is 'Registro de los 40 agentes: contrato, herramientas autorizadas, versión, costes y estado.';
comment on table public.harness_runs is 'Ejecuciones del HARNESS: estado, presupuesto, gasto, plan, aprobación y resultado.';
comment on table public.harness_tasks is 'Tareas del DAG de cada ejecución: agente, fase, dependencias, entradas, salidas, coste e intentos.';
comment on table public.harness_events is 'Traza auditable de cada ejecución (cambios de estado, tareas, herramientas, avisos y errores).';
comment on table public.harness_checkpoints is 'Checkpoints por tarea completada (hash de la salida) para reanudar sin repetir trabajo ni gasto.';
comment on table public.experiences is 'Experiencias generadas: KnowledgePacket verificado + ExperienceSpec, con estado de publicación.';
comment on table public.learning_progress is 'Progreso educativo de cada usuario en cada experiencia (misiones, respuestas, puntos, etapa).';
comment on table public.budget_policies is 'Políticas de presupuesto (global, usuario, investigación, agente, proveedor; diario/mensual/por ejecución).';
comment on table public.cost_ledger is 'Libro de costes: estimaciones, gastos confirmados, tokens, proveedor, modelo y aciertos de caché.';
comment on function public.hybrid_search(text, vector, int, text) is 'Búsqueda textual, semántica o híbrida sobre la biblioteca (respeta RLS). Llamable por RPC.';

-- ######## registro de migraciones (compatible con Supabase CLI) ########
create schema if not exists supabase_migrations;
create table if not exists supabase_migrations.schema_migrations (version text not null primary key, statements text[], name text);
insert into supabase_migrations.schema_migrations (version, name) values
  ('20261109000001', 'core'),
  ('20261109000002', 'rls'),
  ('20261109000003', 'search'),
  ('20261109000004', 'auth_hooks'),
  ('20261110000005', 'supabase_compat')
on conflict (version) do nothing;

commit;

-- Listo. Comprueba en Table Editor que aparecen las 22 tablas.
