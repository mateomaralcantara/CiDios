-- =====================================================================
-- Revisión editorial de afirmaciones (sobre todo las propuestas por un LLM)
-- Solo editor/propietario revisan. Cada decisión queda registrada con el estado anterior.
-- =====================================================================
create table if not exists public.claim_reviews (
  id uuid primary key default gen_random_uuid(),
  claim_id uuid not null references public.claims(id) on delete cascade,
  reviewer_id uuid references auth.users(id) on delete set null,
  action text not null check (action in ('approve','reject','edit')),
  previous jsonb not null default '{}',
  changes jsonb not null default '{}',
  note text not null default '',
  created_at timestamptz not null default now()
);
create index if not exists claim_reviews_claim_idx on public.claim_reviews (claim_id, created_at desc);
comment on table public.claim_reviews is 'Historial de revisión editorial: quién aprobó, corrigió o rechazó cada afirmación, con el estado anterior.';

alter table public.claim_reviews enable row level security;
revoke all on public.claim_reviews from anon, authenticated;
grant select, insert on public.claim_reviews to authenticated;
create policy reviews_staff_read on public.claim_reviews for select to authenticated using (public.is_staff());
create policy reviews_staff_insert on public.claim_reviews for insert to authenticated
  with check (public.is_staff() and reviewer_id = auth.uid());
