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
