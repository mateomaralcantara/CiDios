# Arquitectura

Monolito modular con fronteras funcionales claras; sin microservicios innecesarios.

```
ciencia-de-dios/  (este repositorio)
├── apps/api        FastAPI + Pydantic · HARNESS SUPRA · Evidence Engine · Experience Compiler · worker
│   └── cdd/
│       ├── api/v1.py            API REST versionada (/v1, /v1/admin) + SSE
│       ├── auth.py              Supabase Auth (HS256 o JWKS) + tokens de desarrollo
│       ├── db.py                transacciones con RLS (rol authenticated/anon + request.jwt.claims)
│       ├── library/             pipeline documental, embeddings, búsqueda
│       ├── evidence/            afirmaciones ↔ evidencias ↔ perspectivas, verificación de citas
│       ├── harness/             estados, motor (LangGraph), presupuesto, contexto, registro y agentes
│       ├── experience/          contratos KnowledgePacket/ExperienceSpec, exportación
│       ├── connectors/          OpenAlex, Crossref (descubrimiento bibliográfico)
│       └── security/            detección de inyección de instrucciones
├── apps/web        Next.js 16 · React 19 · TypeScript estricto · Tailwind 4 · PWA
├── supabase/       migraciones SQL (esquema, RLS, búsqueda, hooks de auth) + shim local para pruebas
├── corpus/         corpus semilla verificado (notas editoriales + referencias + afirmaciones)
├── packages/contracts  JSON Schema versionados de los contratos
└── docs/
```

## Flujo de una investigación

```
POST /v1/investigations
  └─ Identity & Policy Engine (authorize) ── CREATED → AUTHORIZED
       └─ cola Postgres (queued) ── Worker (hilo en la API o `python -m cdd.worker`)
            ├─ DAG de arranque (LangGraph): intent → plan → budget          → PLANNED
            │     ├─ ¿supera presupuesto? → BUDGET_EXHAUSTED
            │     └─ ¿supera umbral de aprobación? → AWAITING_APPROVAL
            └─ DAG de investigación (LangGraph, ramas paralelas reales)
                 acquire_* (×N en paralelo)                                  → ACQUIRING
                 analyze                                                     → ANALYZING
                 cross_examine (evidencia contraria, perspectivas)           → CROSS_EXAMINING
                 verify (cita literal contra la fuente)                      → VERIFYING
                 package (KnowledgePacket + sha256)                          → PACKAGING
                 render (ExperienceSpec)                                     → RENDERING
                 qa (contratos e integridad)                                 → QA → READY
  Propietario: approve / pause / resume / cancel / budget / publish          → PUBLISHED
```

Cada tarea: id, estado, presupuesto, herramientas autorizadas, versión del agente, entrada, salida, coste,
intentos, criterio de terminación, checkpoint (sha256 de la salida) y eventos en `harness_events`.

## Separación obligatoria KnowledgePacket → ExperienceSpec → Renderer

- **KnowledgePacket** (`cdd/experience/contracts.py`): afirmaciones verificadas con evidencias, perspectivas, fechas,
  incertidumbres y limitaciones; hash `sha256` canónico.
- **ExperienceSpec**: etapas, eventos, misiones, preguntas, mapa, narración e ilustraciones. Solo **referencia**
  afirmaciones por id; la narración debe ser la afirmación literal.
- **Renderer** (`apps/web/app/experiencias/[id]`): lee los textos desde el paquete por id; nunca los reescribe.
- El agente #37 rechaza cualquier spec que altere afirmaciones o fechas, referencie afirmaciones ajenas o rompa el hash
  (`tests/test_contracts.py`).

## Correspondencia con los motores del mandato

| Motor | Implementación actual |
|---|---|
| A. Identity & Policy | `auth.py`, `engine.authorize`, RLS |
| B. Intent Intelligence | agente #1 (determinista) |
| C. Autonomous Planning | agente #2, DAG con criterios de terminación |
| D. Agent Capability Registry | `harness/registry.py` + tabla `agent_definitions` |
| E. Multi-Agent Orchestrator | `engine.build_graph` (LangGraph) + cola Postgres |
| F. Evidence Acquisition | agente #7 + `library/search.py` + conectores |
| G. Adversarial Research | agente #26 (modo `cross_examine`) |
| H. Epistemic Verification | agente #27 + trigger SQL de citas |
| I. Knowledge Compiler | agente #27 (modo `package`) |
| J. Experience Compiler | agentes #31 y #29 |
| K. Recovery & Checkpoint | `harness_checkpoints`, reintentos, pausa/reanudación |
| L. Continuous Evaluation | agente #37 (QA por ejecución); evaluación continua agregada: pendiente |

## Entornos

`CDD_ENV` = `development` | `test` | `staging` | `production`. Los tokens de desarrollo solo se aceptan en
`development`/`test` con `CDD_DEV_AUTH=true`.
