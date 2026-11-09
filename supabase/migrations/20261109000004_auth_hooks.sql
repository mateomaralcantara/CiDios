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
