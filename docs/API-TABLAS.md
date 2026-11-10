# API de las tablas de Supabase

> Generado automáticamente desde el catálogo de la base con `python -m cdd.export_schema`. No editar a mano.

Cada tabla del esquema `public` queda expuesta por la **API REST de Supabase** (PostgREST) en
`https://<proyecto>.supabase.co/rest/v1/<tabla>` y por `supabase-js`. **RLS decide qué filas ve y modifica cada rol**:

- **visitante** = petición con la clave pública (`anon` / *publishable key*) sin sesión iniciada;
- **usuario autenticado** = petición con la clave pública + el token de sesión (`Authorization: Bearer <access_token>`);
- el **rol de aplicación** (`owner`, `editor`, `user`) está en `user_roles` y lo evalúan las funciones `is_owner()` / `is_staff()`.

La clave `service_role` / *secret key* **ignora RLS**: solo se usa en el backend y **nunca** en el navegador.

Además de la API REST directa, la API propia del proyecto (FastAPI, `/v1/...`) ofrece operaciones de más alto nivel
(investigaciones, HARNESS, misiones calificadas en el servidor, centro de control). Ver `docs/ARCHITECTURE.md`.

## Resumen

| Tabla | Descripción | Visitante | Usuario autenticado |
|---|---|---|---|
| [`agent_definitions`](#agent_definitions) | Registro de los 40 agentes: contrato, herramientas autorizadas, versión, costes y estado. | — | leer (todas las filas); modificar (solo propietario) |
| [`bibliographic_references`](#bibliographic_references) | Referencias bibliográficas externas (libros, artículos, sitios) con estado de verificación del identificador. | leer (todas las filas) | leer (todas las filas); crear (solo editor o propietario); modificar (solo editor o propietario); borrar (solo editor o propietario) |
| [`budget_policies`](#budget_policies) | Políticas de presupuesto (global, usuario, investigación, agente, proveedor; diario/mensual/por ejecución). | — | leer (solo propietario); crear (solo propietario); modificar (solo propietario); borrar (solo propietario) |
| [`claim_reviews`](#claim_reviews) | Historial de revisión editorial: quién aprobó, corrigió o rechazó cada afirmación, con el estado anterior. | — | leer (solo editor o propietario); crear (según condición) |
| [`claims`](#claims) | Afirmaciones con categoría epistémica, disciplina, fechas y su precisión, consenso e incertidumbre. | leer (según condición) | leer (según condición); crear (solo editor o propietario); modificar (solo editor o propietario); borrar (solo editor o propietario) |
| [`cost_ledger`](#cost_ledger) | Libro de costes: estimaciones, gastos confirmados, tokens, proveedor, modelo y aciertos de caché. | — | leer (según condición) |
| [`document_chunks`](#document_chunks) | Fragmentos indexados de cada documento (texto, localizador, tsvector, embedding, riesgo de inyección). | leer (según condición) | leer (según condición); crear (según condición); modificar (según condición); borrar (según condición) |
| [`documents`](#documents) | Documentos de la biblioteca con procedencia, licencia, hash de contenido y estado de revisión. | leer (según condición) | leer (según condición); crear (según condición); modificar (según condición); borrar (según condición) |
| [`entities`](#entities) | Entidades del grafo: personas, lugares, manuscritos, ediciones, conceptos… | leer (todas las filas) | leer (todas las filas); crear (solo editor o propietario); modificar (solo editor o propietario); borrar (solo editor o propietario) |
| [`entity_relations`](#entity_relations) | Relaciones tipadas entre entidades del grafo de conocimiento. | leer (todas las filas) | leer (todas las filas); crear (solo editor o propietario); modificar (solo editor o propietario); borrar (solo editor o propietario) |
| [`evidence_links`](#evidence_links) | Evidencias: fragmento literal de una fuente que respalda, cuestiona, matiza o contextualiza una afirmación. | leer (según condición) | leer (según condición); crear (solo editor o propietario); modificar (solo editor o propietario); borrar (solo editor o propietario) |
| [`experiences`](#experiences) | Experiencias generadas: KnowledgePacket verificado + ExperienceSpec, con estado de publicación. | leer (según condición) | leer (según condición) |
| [`harness_checkpoints`](#harness_checkpoints) | Checkpoints por tarea completada (hash de la salida) para reanudar sin repetir trabajo ni gasto. | — | leer (según condición) |
| [`harness_events`](#harness_events) | Traza auditable de cada ejecución (cambios de estado, tareas, herramientas, avisos y errores). | — | leer (según condición) |
| [`harness_runs`](#harness_runs) | Ejecuciones del HARNESS: estado, presupuesto, gasto, plan, aprobación y resultado. | — | leer (según condición) |
| [`harness_tasks`](#harness_tasks) | Tareas del DAG de cada ejecución: agente, fase, dependencias, entradas, salidas, coste e intentos. | — | leer (según condición) |
| [`investigations`](#investigations) | Investigaciones solicitadas por los usuarios (consulta, preferencias, intención interpretada). | — | leer (según condición); crear (solo las propias); modificar (según condición) |
| [`learning_progress`](#learning_progress) | Progreso educativo de cada usuario en cada experiencia (misiones, respuestas, puntos, etapa). | — | leer (según condición); crear (solo las propias); modificar (solo las propias) |
| [`licenses`](#licenses) | Licencias y derechos de uso de los documentos (qué se puede mostrar, citar o derivar). | leer (todas las filas) | leer (todas las filas); crear (solo editor o propietario); modificar (solo editor o propietario); borrar (solo editor o propietario) |
| [`perspectives`](#perspectives) | Posturas documentadas sobre una afirmación (tradición, quién la sostiene, resumen). | leer (según condición) | leer (según condición); crear (solo editor o propietario); modificar (solo editor o propietario); borrar (solo editor o propietario) |
| [`profiles`](#profiles) | Perfil público de cada usuario de Supabase Auth (nombre, idioma, nivel). | — | leer (según condición); crear (solo las propias); modificar (solo las propias) |
| [`topics`](#topics) | Las 20 áreas de la enciclopedia y sus preguntas abiertas. | leer (todas las filas) | leer (todas las filas); crear (solo editor o propietario); modificar (solo editor o propietario); borrar (solo editor o propietario) |
| [`user_roles`](#user_roles) | Rol de aplicación por usuario (owner, editor, user). Solo el propietario lo modifica. | — | leer (según condición); crear (solo propietario); modificar (solo propietario); borrar (solo propietario) |

Calculado a partir de los permisos de la tabla y de sus políticas RLS. «Según condición» = ver la política exacta en la sección de la tabla.

## agent_definitions

Registro de los 40 agentes: contrato, herramientas autorizadas, versión, costes y estado.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `code` | `text` | no |  |
| `number` | `integer` | no |  |
| `family` | `text` | no |  |
| `name_es` | `text` | no |  |
| `version` | `text` | no |  |
| `status` | `text` | no |  |
| `enabled` | `boolean` | no | `true` |
| `execution_model` | `text` | no |  |
| `allowed_tools` | `text[]` | no | `'{}'::text[]` |
| `input_contract` | `text` | no |  |
| `output_contract` | `text` | no |  |
| `rules` | `text[]` | no | `'{}'::text[]` |
| `unit_cost_usd` | `numeric(12,6)` | no | `0` |
| `max_cost_per_run_usd` | `numeric(12,6)` | no | `1` |
| `fallback` | `text` | no | `''::text` |
| `updated_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Primaria: `PRIMARY KEY (code)`
- Única: `UNIQUE (number)`

**Políticas RLS**

- `agents_read` — usuario autenticado puede **leer** si `true`
- `agents_write` — usuario autenticado puede **modificar** si `is_owner()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/agent_definitions?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('agent_definitions').select('*').limit(10)
```

## bibliographic_references

Referencias bibliográficas externas (libros, artículos, sitios) con estado de verificación del identificador.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `slug` | `text` | no |  |
| `ref_type` | `text` | no |  |
| `authors` | `text[]` | no | `'{}'::text[]` |
| `title` | `text` | no |  |
| `container_title` | `text` | sí |  |
| `publisher` | `text` | sí |  |
| `year` | `integer` | sí |  |
| `edition` | `text` | sí |  |
| `language` | `text` | sí |  |
| `identifiers` | `jsonb` | no | `'{}'::jsonb` |
| `identifier_check` | `text` | no | `'unverified_offline'::text` |
| `checked_at` | `timestamp with time zone` | sí |  |
| `created_at` | `timestamp with time zone` | no | `now()` |
| `tier` | `text` | no | `'published'::text` |
| `doi` | `text` | sí |  |
| `url` | `text` | sí |  |
| `openalex_id` | `text` | sí |  |
| `venue_type` | `text` | sí |  |
| `cited_by_count` | `integer` | sí |  |
| `is_retracted` | `boolean` | no | `false` |
| `retraction_checked_at` | `timestamp with time zone` | sí |  |
| `source_connector` | `text` | sí |  |

**Claves y relaciones**

- Primaria: `PRIMARY KEY (id)`
- Única: `UNIQUE (slug)`

**Políticas RLS**

- `refs_read` — visitante, usuario autenticado puede **leer** si `true`
- `refs_write` — usuario autenticado puede **leer y escribir** si `is_staff()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/bibliographic_references?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('bibliographic_references').select('*').limit(10)
```

## budget_policies

Políticas de presupuesto (global, usuario, investigación, agente, proveedor; diario/mensual/por ejecución).

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `scope` | `text` | no |  |
| `scope_ref` | `text` | no | `'*'::text` |
| `period` | `text` | no |  |
| `limit_usd` | `numeric(12,6)` | no |  |
| `auto_approve_below_usd` | `numeric(12,6)` | no | `0.50` |
| `active` | `boolean` | no | `true` |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Primaria: `PRIMARY KEY (id)`
- Única: `UNIQUE (scope, scope_ref, period)`

**Políticas RLS**

- `budgets_owner` — usuario autenticado puede **leer y escribir** si `is_owner()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/budget_policies?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('budget_policies').select('*').limit(10)
```

## claim_reviews

Historial de revisión editorial: quién aprobó, corrigió o rechazó cada afirmación, con el estado anterior.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `claim_id` | `uuid` | no |  |
| `reviewer_id` | `uuid` | sí |  |
| `action` | `text` | no |  |
| `previous` | `jsonb` | no | `'{}'::jsonb` |
| `changes` | `jsonb` | no | `'{}'::jsonb` |
| `note` | `text` | no | `''::text` |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (reviewer_id) REFERENCES auth.users(id) ON DELETE SET NULL`
- Foránea: `FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (id)`

**Políticas RLS**

- `reviews_staff_insert` — usuario autenticado puede **crear** si `(is_staff() AND (reviewer_id = auth.uid()))`
- `reviews_staff_read` — usuario autenticado puede **leer** si `is_staff()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/claim_reviews?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('claim_reviews').select('*').limit(10)
```

## claims

Afirmaciones con categoría epistémica, disciplina, fechas y su precisión, consenso e incertidumbre.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `slug` | `text` | no |  |
| `topic_id` | `uuid` | sí |  |
| `statement` | `text` | no |  |
| `asserted_by` | `text` | no | `''::text` |
| `discipline` | `text` | no |  |
| `category` | `epistemic_category` | no |  |
| `is_event` | `boolean` | no | `false` |
| `date_start` | `integer` | sí |  |
| `date_end` | `integer` | sí |  |
| `date_precision` | `date_precision` | no | `'unknown'::date_precision` |
| `date_label` | `text` | no | `''::text` |
| `place_entity_id` | `uuid` | sí |  |
| `subject_entity_id` | `uuid` | sí |  |
| `consensus_note` | `text` | no | `''::text` |
| `insufficient_evidence_note` | `text` | no | `''::text` |
| `future_research_note` | `text` | no | `''::text` |
| `review_status` | `review_status` | no | `'draft'::review_status` |
| `visibility` | `visibility` | no | `'public'::visibility` |
| `content_sha256` | `text` | no |  |
| `created_by` | `uuid` | sí |  |
| `created_at` | `timestamp with time zone` | no | `now()` |
| `updated_at` | `timestamp with time zone` | no | `now()` |
| `origin` | `text` | no | `'curated'::text` |
| `generated_by` | `jsonb` | no | `'{}'::jsonb` |
| `run_id` | `uuid` | sí |  |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (created_by) REFERENCES auth.users(id) ON DELETE SET NULL`
- Foránea: `FOREIGN KEY (place_entity_id) REFERENCES entities(id) ON DELETE SET NULL`
- Foránea: `FOREIGN KEY (subject_entity_id) REFERENCES entities(id) ON DELETE SET NULL`
- Foránea: `FOREIGN KEY (run_id) REFERENCES harness_runs(id) ON DELETE SET NULL`
- Foránea: `FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE SET NULL`
- Primaria: `PRIMARY KEY (id)`
- Única: `UNIQUE (slug)`

**Políticas RLS**

- `claims_read` — visitante, usuario autenticado puede **leer** si `(((visibility = 'public'::visibility) AND (review_status <> 'rejected'::review_status)) OR (created_by = auth.uid()) OR is_staff())`
- `claims_write` — usuario autenticado puede **leer y escribir** si `is_staff()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/claims?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('claims').select('*').limit(10)
```

## cost_ledger

Libro de costes: estimaciones, gastos confirmados, tokens, proveedor, modelo y aciertos de caché.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `bigint` | no | `nextval('cost_ledger_id_seq'::regclass)` |
| `run_id` | `uuid` | sí |  |
| `user_id` | `uuid` | sí |  |
| `agent_code` | `text` | sí |  |
| `provider` | `text` | no | `'local'::text` |
| `model` | `text` | no | `'deterministic'::text` |
| `kind` | `text` | no |  |
| `input_tokens` | `integer` | no | `0` |
| `output_tokens` | `integer` | no | `0` |
| `amount_usd` | `numeric(12,6)` | no | `0` |
| `cache_hit` | `boolean` | no | `false` |
| `note` | `text` | no | `''::text` |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE SET NULL`
- Foránea: `FOREIGN KEY (run_id) REFERENCES harness_runs(id) ON DELETE SET NULL`
- Primaria: `PRIMARY KEY (id)`

**Políticas RLS**

- `ledger_read` — usuario autenticado puede **leer** si `((user_id = auth.uid()) OR is_owner())`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/cost_ledger?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('cost_ledger').select('*').limit(10)
```

## document_chunks

Fragmentos indexados de cada documento (texto, localizador, tsvector, embedding, riesgo de inyección).

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `document_id` | `uuid` | no |  |
| `ordinal` | `integer` | no |  |
| `locator` | `text` | no | `''::text` |
| `content` | `text` | no |  |
| `content_tsv` | `tsvector` | sí |  |
| `embedding` | `vector(384)` | sí |  |
| `embedding_model` | `text` | no | `''::text` |
| `injection_risk` | `boolean` | no | `false` |
| `injection_signals` | `text[]` | no | `'{}'::text[]` |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (id)`
- Única: `UNIQUE (document_id, ordinal)`

**Políticas RLS**

- `chunks_read` — visitante, usuario autenticado puede **leer** si `(EXISTS ( SELECT 1
   FROM documents d
  WHERE (d.id = document_chunks.document_id)))`
- `chunks_write` — usuario autenticado puede **leer y escribir** si `(EXISTS ( SELECT 1
   FROM documents d
  WHERE ((d.id = document_chunks.document_id) AND (is_staff() OR (d.owner_id = auth.uid())))))`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/document_chunks?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('document_chunks').select('*').limit(10)
```

## documents

Documentos de la biblioteca con procedencia, licencia, hash de contenido y estado de revisión.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `slug` | `text` | sí |  |
| `title` | `text` | no |  |
| `doc_kind` | `text` | no |  |
| `authors` | `text[]` | no | `'{}'::text[]` |
| `institution` | `text` | sí |  |
| `published_date` | `text` | sí |  |
| `language` | `text` | no | `'es'::text` |
| `edition` | `text` | sí |  |
| `identifier` | `text` | sí |  |
| `license_code` | `text` | no |  |
| `rights_statement` | `text` | no | `''::text` |
| `provenance` | `jsonb` | no | `'{}'::jsonb` |
| `consulted_at` | `timestamp with time zone` | sí |  |
| `content_sha256` | `text` | no |  |
| `body` | `text` | no |  |
| `owner_id` | `uuid` | sí |  |
| `visibility` | `visibility` | no | `'private'::visibility` |
| `review_status` | `review_status` | no | `'draft'::review_status` |
| `cites` | `uuid[]` | no | `'{}'::uuid[]` |
| `created_at` | `timestamp with time zone` | no | `now()` |
| `updated_at` | `timestamp with time zone` | no | `now()` |
| `source_tier` | `text` | no | `'editorial'::text` |
| `doi` | `text` | sí |  |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (license_code) REFERENCES licenses(code)`
- Foránea: `FOREIGN KEY (owner_id) REFERENCES auth.users(id) ON DELETE SET NULL`
- Primaria: `PRIMARY KEY (id)`
- Única: `UNIQUE (content_sha256)`
- Única: `UNIQUE (slug)`

**Políticas RLS**

- `documents_delete` — usuario autenticado puede **borrar** si `(is_staff() OR (owner_id = auth.uid()))`
- `documents_insert` — usuario autenticado puede **crear** si `(is_staff() OR ((owner_id = auth.uid()) AND (visibility = 'private'::visibility) AND (doc_kind = 'user_upload'::text)))`
- `documents_read_own` — usuario autenticado puede **leer** si `((owner_id = auth.uid()) OR is_staff())`
- `documents_read_public` — visitante, usuario autenticado puede **leer** si `((visibility = 'public'::visibility) AND (review_status <> 'rejected'::review_status))`
- `documents_update` — usuario autenticado puede **modificar** si `(is_staff() OR (owner_id = auth.uid()))`; al escribir: `(is_staff() OR ((owner_id = auth.uid()) AND (visibility = 'private'::visibility)))`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/documents?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('documents').select('*').limit(10)
```

## entities

Entidades del grafo: personas, lugares, manuscritos, ediciones, conceptos…

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `slug` | `text` | no |  |
| `kind` | `entity_kind` | no |  |
| `name` | `text` | no |  |
| `description` | `text` | no | `''::text` |
| `attributes` | `jsonb` | no | `'{}'::jsonb` |
| `topic_id` | `uuid` | sí |  |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (topic_id) REFERENCES topics(id) ON DELETE SET NULL`
- Primaria: `PRIMARY KEY (id)`
- Única: `UNIQUE (slug)`

**Políticas RLS**

- `entities_read` — visitante, usuario autenticado puede **leer** si `true`
- `entities_write` — usuario autenticado puede **leer y escribir** si `is_staff()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/entities?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('entities').select('*').limit(10)
```

## entity_relations

Relaciones tipadas entre entidades del grafo de conocimiento.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `subject_id` | `uuid` | no |  |
| `predicate` | `text` | no |  |
| `object_id` | `uuid` | no |  |
| `evidence_claim_id` | `uuid` | sí |  |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (subject_id) REFERENCES entities(id) ON DELETE CASCADE`
- Foránea: `FOREIGN KEY (evidence_claim_id) REFERENCES claims(id) ON DELETE SET NULL`
- Foránea: `FOREIGN KEY (object_id) REFERENCES entities(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (id)`
- Única: `UNIQUE (subject_id, predicate, object_id)`

**Políticas RLS**

- `relations_read` — visitante, usuario autenticado puede **leer** si `true`
- `relations_write` — usuario autenticado puede **leer y escribir** si `is_staff()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/entity_relations?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('entity_relations').select('*').limit(10)
```

## evidence_links

Evidencias: fragmento literal de una fuente que respalda, cuestiona, matiza o contextualiza una afirmación.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `claim_id` | `uuid` | no |  |
| `chunk_id` | `uuid` | no |  |
| `reference_id` | `uuid` | sí |  |
| `stance` | `evidence_stance` | no |  |
| `exact_fragment` | `text` | no |  |
| `locator` | `text` | no | `''::text` |
| `note` | `text` | no | `''::text` |
| `verification_status` | `text` | no | `'unverified'::text` |
| `verified_at` | `timestamp with time zone` | sí |  |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE`
- Foránea: `FOREIGN KEY (chunk_id) REFERENCES document_chunks(id) ON DELETE RESTRICT`
- Foránea: `FOREIGN KEY (reference_id) REFERENCES bibliographic_references(id) ON DELETE SET NULL`
- Primaria: `PRIMARY KEY (id)`

**Políticas RLS**

- `evidence_read` — visitante, usuario autenticado puede **leer** si `(EXISTS ( SELECT 1
   FROM claims c
  WHERE (c.id = evidence_links.claim_id)))`
- `evidence_write` — usuario autenticado puede **leer y escribir** si `is_staff()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/evidence_links?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('evidence_links').select('*').limit(10)
```

## experiences

Experiencias generadas: KnowledgePacket verificado + ExperienceSpec, con estado de publicación.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `run_id` | `uuid` | sí |  |
| `owner_id` | `uuid` | no |  |
| `modality` | `text` | no |  |
| `title` | `text` | no |  |
| `knowledge_packet` | `jsonb` | no |  |
| `knowledge_packet_sha256` | `text` | no |  |
| `experience_spec` | `jsonb` | no |  |
| `status` | `text` | no | `'draft'::text` |
| `published_by` | `uuid` | sí |  |
| `published_at` | `timestamp with time zone` | sí |  |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (run_id) REFERENCES harness_runs(id) ON DELETE SET NULL`
- Foránea: `FOREIGN KEY (owner_id) REFERENCES auth.users(id) ON DELETE CASCADE`
- Foránea: `FOREIGN KEY (published_by) REFERENCES auth.users(id)`
- Primaria: `PRIMARY KEY (id)`

**Políticas RLS**

- `experiences_read_own` — usuario autenticado puede **leer** si `((owner_id = auth.uid()) OR is_staff())`
- `experiences_read_published` — visitante, usuario autenticado puede **leer** si `(status = 'published'::text)`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/experiences?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('experiences').select('*').limit(10)
```

## harness_checkpoints

Checkpoints por tarea completada (hash de la salida) para reanudar sin repetir trabajo ni gasto.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `run_id` | `uuid` | no |  |
| `task_key` | `text` | no |  |
| `state` | `run_state` | no |  |
| `output_sha256` | `text` | no |  |
| `snapshot` | `jsonb` | no |  |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (run_id) REFERENCES harness_runs(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (id)`
- Única: `UNIQUE (run_id, task_key)`

**Políticas RLS**

- `checkpoints_read` — usuario autenticado puede **leer** si `(EXISTS ( SELECT 1
   FROM harness_runs r
  WHERE (r.id = harness_checkpoints.run_id)))`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/harness_checkpoints?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('harness_checkpoints').select('*').limit(10)
```

## harness_events

Traza auditable de cada ejecución (cambios de estado, tareas, herramientas, avisos y errores).

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `bigint` | no | `nextval('harness_events_id_seq'::regclass)` |
| `run_id` | `uuid` | no |  |
| `task_key` | `text` | sí |  |
| `level` | `text` | no | `'info'::text` |
| `event_type` | `text` | no |  |
| `message` | `text` | no |  |
| `data` | `jsonb` | no | `'{}'::jsonb` |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (run_id) REFERENCES harness_runs(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (id)`

**Políticas RLS**

- `events_read` — usuario autenticado puede **leer** si `(EXISTS ( SELECT 1
   FROM harness_runs r
  WHERE (r.id = harness_events.run_id)))`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/harness_events?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('harness_events').select('*').limit(10)
```

## harness_runs

Ejecuciones del HARNESS: estado, presupuesto, gasto, plan, aprobación y resultado.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `investigation_id` | `uuid` | no |  |
| `owner_id` | `uuid` | no |  |
| `state` | `run_state` | no | `'CREATED'::run_state` |
| `previous_state` | `run_state` | sí |  |
| `budget_usd` | `numeric(12,6)` | no | `1` |
| `spent_usd` | `numeric(12,6)` | no | `0` |
| `estimated_usd` | `numeric(12,6)` | no | `0` |
| `requires_approval` | `boolean` | no | `false` |
| `approved_by` | `uuid` | sí |  |
| `approved_at` | `timestamp with time zone` | sí |  |
| `pause_requested` | `boolean` | no | `false` |
| `cancel_requested` | `boolean` | no | `false` |
| `queued` | `boolean` | no | `false` |
| `worker_lease_until` | `timestamp with time zone` | sí |  |
| `plan` | `jsonb` | no | `'{}'::jsonb` |
| `result` | `jsonb` | no | `'{}'::jsonb` |
| `error` | `text` | sí |  |
| `contract_version` | `text` | no | `'1.0.0'::text` |
| `created_at` | `timestamp with time zone` | no | `now()` |
| `updated_at` | `timestamp with time zone` | no | `now()` |
| `finished_at` | `timestamp with time zone` | sí |  |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (approved_by) REFERENCES auth.users(id)`
- Foránea: `FOREIGN KEY (investigation_id) REFERENCES investigations(id) ON DELETE CASCADE`
- Foránea: `FOREIGN KEY (owner_id) REFERENCES auth.users(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (id)`

**Políticas RLS**

- `runs_read` — usuario autenticado puede **leer** si `((owner_id = auth.uid()) OR is_owner())`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/harness_runs?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('harness_runs').select('*').limit(10)
```

## harness_tasks

Tareas del DAG de cada ejecución: agente, fase, dependencias, entradas, salidas, coste e intentos.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `run_id` | `uuid` | no |  |
| `task_key` | `text` | no |  |
| `agent_code` | `text` | no |  |
| `phase` | `run_state` | no |  |
| `depends_on` | `text[]` | no | `'{}'::text[]` |
| `status` | `task_status` | no | `'pending'::task_status` |
| `attempts` | `integer` | no | `0` |
| `max_attempts` | `integer` | no | `2` |
| `budget_usd` | `numeric(12,6)` | no | `0` |
| `cost_usd` | `numeric(12,6)` | no | `0` |
| `allowed_tools` | `text[]` | no | `'{}'::text[]` |
| `agent_version` | `text` | no | `''::text` |
| `input` | `jsonb` | no | `'{}'::jsonb` |
| `output` | `jsonb` | no | `'{}'::jsonb` |
| `completion_criteria` | `text` | no | `''::text` |
| `error` | `text` | sí |  |
| `started_at` | `timestamp with time zone` | sí |  |
| `finished_at` | `timestamp with time zone` | sí |  |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (agent_code) REFERENCES agent_definitions(code)`
- Foránea: `FOREIGN KEY (run_id) REFERENCES harness_runs(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (id)`
- Única: `UNIQUE (run_id, task_key)`

**Políticas RLS**

- `tasks_read` — usuario autenticado puede **leer** si `(EXISTS ( SELECT 1
   FROM harness_runs r
  WHERE (r.id = harness_tasks.run_id)))`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/harness_tasks?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('harness_tasks').select('*').limit(10)
```

## investigations

Investigaciones solicitadas por los usuarios (consulta, preferencias, intención interpretada).

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `owner_id` | `uuid` | no |  |
| `prompt` | `text` | no |  |
| `prompt_sha256` | `text` | no |  |
| `preferences` | `jsonb` | no | `'{}'::jsonb` |
| `intent` | `jsonb` | no | `'{}'::jsonb` |
| `status` | `text` | no | `'open'::text` |
| `created_at` | `timestamp with time zone` | no | `now()` |
| `updated_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (owner_id) REFERENCES auth.users(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (id)`

**Políticas RLS**

- `inv_insert` — usuario autenticado puede **crear** si `(owner_id = auth.uid())`
- `inv_select` — usuario autenticado puede **leer** si `((owner_id = auth.uid()) OR is_owner())`
- `inv_update` — usuario autenticado puede **modificar** si `((owner_id = auth.uid()) OR is_owner())`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/investigations?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('investigations').select('*').limit(10)
```

## learning_progress

Progreso educativo de cada usuario en cada experiencia (misiones, respuestas, puntos, etapa).

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `user_id` | `uuid` | no |  |
| `experience_id` | `uuid` | no |  |
| `completed_missions` | `text[]` | no | `'{}'::text[]` |
| `answers` | `jsonb` | no | `'{}'::jsonb` |
| `score` | `integer` | no | `0` |
| `unlocked_stage` | `integer` | no | `0` |
| `updated_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE`
- Foránea: `FOREIGN KEY (experience_id) REFERENCES experiences(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (id)`
- Única: `UNIQUE (user_id, experience_id)`

**Políticas RLS**

- `progress_insert` — usuario autenticado puede **crear** si `((user_id = auth.uid()) AND (EXISTS ( SELECT 1
   FROM experiences e
  WHERE (e.id = learning_progress.experience_id))))`
- `progress_select` — usuario autenticado puede **leer** si `((user_id = auth.uid()) OR is_owner())`
- `progress_update` — usuario autenticado puede **modificar** si `(user_id = auth.uid())`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/learning_progress?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('learning_progress').select('*').limit(10)
```

## licenses

Licencias y derechos de uso de los documentos (qué se puede mostrar, citar o derivar).

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `code` | `text` | no |  |
| `name` | `text` | no |  |
| `url` | `text` | sí |  |
| `allows_display` | `boolean` | no | `true` |
| `allows_excerpt` | `boolean` | no | `true` |
| `allows_full_text` | `boolean` | no | `false` |
| `allows_derivatives` | `boolean` | no | `false` |
| `requires_attribution` | `boolean` | no | `true` |
| `notes` | `text` | no | `''::text` |

**Claves y relaciones**

- Primaria: `PRIMARY KEY (code)`

**Políticas RLS**

- `licenses_read` — visitante, usuario autenticado puede **leer** si `true`
- `licenses_write` — usuario autenticado puede **leer y escribir** si `is_staff()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/licenses?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('licenses').select('*').limit(10)
```

## perspectives

Posturas documentadas sobre una afirmación (tradición, quién la sostiene, resumen).

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `claim_id` | `uuid` | no |  |
| `label` | `text` | no |  |
| `tradition` | `text` | no |  |
| `summary` | `text` | no |  |
| `held_by` | `text` | no | `''::text` |
| `evidence_link_ids` | `uuid[]` | no | `'{}'::uuid[]` |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (claim_id) REFERENCES claims(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (id)`

**Políticas RLS**

- `perspectives_read` — visitante, usuario autenticado puede **leer** si `(EXISTS ( SELECT 1
   FROM claims c
  WHERE (c.id = perspectives.claim_id)))`
- `perspectives_write` — usuario autenticado puede **leer y escribir** si `is_staff()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/perspectives?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('perspectives').select('*').limit(10)
```

## profiles

Perfil público de cada usuario de Supabase Auth (nombre, idioma, nivel).

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no |  |
| `display_name` | `text` | no | `''::text` |
| `preferred_language` | `text` | no | `'es'::text` |
| `academic_level` | `text` | no | `'general'::text` |
| `created_at` | `timestamp with time zone` | no | `now()` |
| `updated_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (id) REFERENCES auth.users(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (id)`

**Políticas RLS**

- `profiles_insert` — usuario autenticado puede **crear** si `(id = auth.uid())`
- `profiles_select` — usuario autenticado puede **leer** si `((id = auth.uid()) OR is_staff())`
- `profiles_update` — usuario autenticado puede **modificar** si `(id = auth.uid())`
- Columnas que un usuario puede modificar: preferred_language, display_name, academic_level

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/profiles?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('profiles').select('*').limit(10)
```

## topics

Las 20 áreas de la enciclopedia y sus preguntas abiertas.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `id` | `uuid` | no | `gen_random_uuid()` |
| `slug` | `text` | no |  |
| `title` | `text` | no |  |
| `summary` | `text` | no | `''::text` |
| `sort_order` | `integer` | no | `0` |
| `content_status` | `text` | no | `'empty'::text` |
| `open_questions` | `text[]` | no | `'{}'::text[]` |
| `created_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Primaria: `PRIMARY KEY (id)`
- Única: `UNIQUE (slug)`

**Políticas RLS**

- `topics_read` — visitante, usuario autenticado puede **leer** si `true`
- `topics_write` — usuario autenticado puede **leer y escribir** si `is_staff()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/topics?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('topics').select('*').limit(10)
```

## user_roles

Rol de aplicación por usuario (owner, editor, user). Solo el propietario lo modifica.

RLS: **activado**

| Columna | Tipo | Nulo | Por defecto |
|---|---|---|---|
| `user_id` | `uuid` | no |  |
| `role` | `app_role` | no | `'user'::app_role` |
| `granted_by` | `uuid` | sí |  |
| `granted_at` | `timestamp with time zone` | no | `now()` |

**Claves y relaciones**

- Foránea: `FOREIGN KEY (granted_by) REFERENCES auth.users(id)`
- Foránea: `FOREIGN KEY (user_id) REFERENCES auth.users(id) ON DELETE CASCADE`
- Primaria: `PRIMARY KEY (user_id)`

**Políticas RLS**

- `roles_select` — usuario autenticado puede **leer** si `((user_id = auth.uid()) OR is_owner())`
- `roles_write` — usuario autenticado puede **leer y escribir** si `is_owner()`

**Ejemplos**

```bash
curl "$SUPABASE_URL/rest/v1/user_roles?select=*&limit=10" \
  -H "apikey: $SUPABASE_ANON_KEY" -H "Authorization: Bearer $ACCESS_TOKEN"
```

```ts
const { data, error } = await supabase.from('user_roles').select('*').limit(10)
```

## Funciones (RPC)

### current_app_role



- Argumentos: `—`
- Devuelve: `app_role`

### hybrid_search

Búsqueda textual, semántica o híbrida sobre la biblioteca (respeta RLS). Llamable por RPC.

- Argumentos: `query_text text, query_embedding vector, match_count integer DEFAULT 10, mode text DEFAULT 'hybrid'::text, embedding_model text DEFAULT NULL::text`
- Devuelve: `TABLE(chunk_id uuid, document_id uuid, document_title text, locator text, content text, text_rank real, semantic_score real, score real, injection_risk boolean)`

### is_owner



- Argumentos: `—`
- Devuelve: `boolean`

### is_staff



- Argumentos: `—`
- Devuelve: `boolean`

```ts
const { data } = await supabase.rpc('hybrid_search', {
  query_text: 'Códice de Leningrado', query_embedding: null, match_count: 10, mode: 'text' })
```

La búsqueda semántica necesita el vector de la consulta (384 dimensiones), que calcula el backend: usa
`GET /v1/library/search?q=...&mode=hybrid` de la API del proyecto para búsquedas híbridas.

## Tipos enumerados

- `app_role`: `owner`, `editor`, `user`
- `date_precision`: `exact_day`, `exact_year`, `approximate_year`, `range`, `decade`, `century`, `disputed`, `unknown`
- `entity_kind`: `person`, `place`, `manuscript`, `edition`, `event`, `concept`, `tradition`, `institution`, `theory`, `hypothesis`, `artifact`, `period`
- `epistemic_category`: `empirical_fact`, `historical_document`, `scholarly_consensus`, `scientific_hypothesis`, `philosophical_argument`, `theological_interpretation`, `religious_belief`, `contested`, `uncorroborated`, `open_question`
- `evidence_stance`: `supports`, `challenges`, `contextualizes`, `qualifies`
- `review_status`: `draft`, `pending_review`, `reviewed`, `rejected`
- `run_state`: `CREATED`, `AUTHORIZED`, `PLANNED`, `ACQUIRING`, `ANALYZING`, `CROSS_EXAMINING`, `VERIFYING`, `PACKAGING`, `RENDERING`, `QA`, `READY`, `PUBLISHED`, `FAILED`, `CANCELLED`, `PAUSED`, `AWAITING_APPROVAL`, `LICENSE_BLOCKED`, `PARTIAL`, `BUDGET_EXHAUSTED`
- `task_status`: `pending`, `queued`, `running`, `succeeded`, `failed`, `skipped`, `cancelled`, `blocked`
- `visibility`: `public`, `private`
