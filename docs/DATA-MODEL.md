# Modelo de datos: 76 tablas en 9 dominios

Diseño completo. ✅ = implementado en `supabase/migrations/` (núcleo de **22 tablas**; el mínimo exigido era 18).
Las demás están diseñadas y se incorporarán por fases (ver `ROADMAP.md`). Todas las tablas expuestas tendrán RLS
con `enable` + `force row level security` y políticas explícitas, como las 22 actuales.

| Dominio | Nº | Tablas |
|---|---:|---|
| 1. Identidad y autorización | 7 | ✅ `profiles`, ✅ `user_roles`, `organizations`, `memberships`, `api_keys`, `consents`, `access_audit` |
| 2. Fuentes documentales | 10 | ✅ `licenses`, ✅ `bibliographic_references`, ✅ `documents`, ✅ `document_chunks`, `document_versions`, `source_connectors`, `connector_runs`, `acquisition_requests`, `normalized_identifiers`, `provenance_records` |
| 3. Ontología y evidencias | 10 | ✅ `topics`, ✅ `entities`, ✅ `entity_relations`, ✅ `claims`, ✅ `evidence_links`, ✅ `perspectives`, `claim_versions`, `arguments`, `argument_edges`, `consensus_assessments` |
| 4. Investigación | 8 | ✅ `investigations`, `research_questions`, `research_reports`, `report_sections`, `research_notes`, `review_requests`, `expert_reviews`, `collections` |
| 5. HARNESS | 12 | ✅ `agent_definitions`, ✅ `harness_runs`, ✅ `harness_tasks`, ✅ `harness_events`, ✅ `harness_checkpoints`, `agent_versions`, `tool_definitions`, `agent_tool_grants`, `approvals`, `task_artifacts`, `prompt_templates`, `agent_evaluations` |
| 6. Experiencias | 11 | ✅ `experiences`, `experience_versions`, `timelines`, `timeline_events`, `maps`, `map_layers`, `debates`, `lessons`, `simulations`, `renders`, `experience_feedback` |
| 7. Multimedia | 6 | `media_assets`, `media_provenance`, `media_generation_jobs`, `narrations`, `transcripts`, `media_licenses` |
| 8. Educación | 6 | ✅ `learning_progress`, `courses`, `course_modules`, `enrollments`, `quiz_attempts`, `badges` |
| 9. Operaciones y evaluación | 6 | ✅ `budget_policies`, ✅ `cost_ledger`, `model_providers`, `model_catalog`, `evaluation_runs`, `evaluation_results` |
| **Total** | **76** | **22 implementadas** |

## Decisiones del núcleo

- **Roles separados del perfil** (`user_roles`): un usuario puede editar su perfil pero nunca su rol. Solo el propietario asigna roles.
- **Citas no fabricables**: el trigger `evidence_fragment_check` rechaza en la base de datos cualquier `evidence_link` cuyo `exact_fragment` no aparezca literalmente en el fragmento citado.
- **Categoría epistémica obligatoria** (`epistemic_category`, 10 valores) y **precisión de fecha** (`date_precision`). No existe una "puntuación de verdad".
- **Fechas**: año histórico, negativo = a. e. c. (no existe año 0), con `date_label` legible y `date_precision`.
- **Búsqueda**: `tsvector` con configuración `es_unaccent` + `vector(384)` con índice HNSW; `hybrid_search()` es `security invoker` y respeta RLS.
- **Cola del HARNESS en Postgres**: `harness_runs.queued` + `worker_lease_until` con `for update skip locked`.
- **Presupuesto**: reserva atómica bajo bloqueo de fila de la ejecución (ramas paralelas no pueden superarlo juntas).
- **Experiencias**: guardan el `knowledge_packet` y su `sha256` junto al `experience_spec`; el control de calidad verifica la integridad.

## Matriz RLS (resumen)

| Tabla | Visitante | Usuario | Editor | Propietario |
|---|---|---|---|---|
| catálogo (`topics`, `entities`, `claims`, `evidence_links`, `perspectives`, `licenses`, referencias) | lee público | lee público | lee/escribe | lee/escribe |
| `documents`, `document_chunks` | públicos | públicos + propios privados; inserta solo privados `user_upload` | todo | todo |
| `investigations`, `harness_*` | — | solo propios (sin escritura directa) | propios | todos |
| `experiences` | publicadas | publicadas + propias | todas | todas |
| `learning_progress` | — | solo propio | propio | todos (lectura) |
| `cost_ledger` | — | solo propio | propio | todo |
| `budget_policies`, `user_roles` (escritura) | — | — | — | sí |

Pruebas: `apps/api/tests/test_rls.py` (visitante, usuario, accesos cruzados, escalada de rol, citas fabricadas).
