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
