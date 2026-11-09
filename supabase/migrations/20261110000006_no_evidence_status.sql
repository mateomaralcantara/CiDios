-- Estado de investigación «no_evidence»: la biblioteca no tenía evidencia pertinente y no se generó contenido.
alter table public.investigations drop constraint if exists investigations_status_check;
alter table public.investigations add constraint investigations_status_check
  check (status in ('open','running','ready','published','archived','failed','no_evidence'));
