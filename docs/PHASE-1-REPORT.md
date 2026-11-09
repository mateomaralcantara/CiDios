# Informe de la fase 1: MVP funcional

Fecha: 2026-11-09. Alcance: sección 12 (MVP) y sección 13 (prueba final) del mandato.

## Entregado (código real, probado)

| # | Requisito del MVP | Estado | Evidencia |
|---|---|---|---|
| 1 | Plataforma web independiente | ✅ | `apps/web` (Next.js 16, TS estricto, Tailwind, PWA); build de producción correcto |
| 2 | Backend FastAPI | ✅ | `apps/api`, API `/v1` versionada |
| 3 | Proyecto Supabase propio | ⚠️ preparado | migraciones + `config.toml`; **no se creó un proyecto real** (sin credenciales ni red hacia Supabase). Probado sobre Postgres 16 + pgvector con un shim de Supabase |
| 4 | Autenticación | ✅ | JWT de Supabase (HS256/JWKS) + tokens de desarrollo; trigger de alta de usuarios |
| 5 | Biblioteca documental | ✅ | pipeline de ingesta (licencia, normalización, deduplicación, fragmentación, indexación, detección de inyección) |
| 6 | Búsqueda textual y semántica | ✅ | FTS en español + pgvector + híbrida RRF. Embeddings: modelo **léxico local** (no neuronal) |
| 7 | Fuentes verificables | ✅ | 57 citas literales verificadas por trigger SQL y por el agente #27 |
| 8 | Seis agentes operativos | ✅ 9 | #1, #2, #5, #7, #26, #27, #29, #31, #37 |
| 9 | Planificación y seguimiento | ✅ | DAG en LangGraph, estados, SSE, checkpoints, pausa/reanudación/cancelación |
| 10 | Motor de afirmaciones y evidencias | ✅ | 10 categorías epistémicas, posturas, consenso, límites |
| 11 | Comparador de perspectivas | ✅ | `/v1/topics/{slug}/compare` y pestaña en el artículo |
| 12 | Artículos enciclopédicos | ✅ | `/areas/[slug]` |
| 13 | Líneas de tiempo navegables | ✅ | modo académico |
| 14 | Línea de tiempo gamificada | ✅ | 5 etapas, 15 preguntas, calificación en el servidor, desbloqueo y progreso |
| 15 | Panel administrador | ✅ | `/admin` (9 pestañas) |
| 16 | Control de presupuestos | ✅ | políticas, reserva atómica, aprobación, bloqueo |
| 17 | Historial de ejecución | ✅ | `harness_events`, `harness_checkpoints`, `cost_ledger` |
| 18 | Pruebas automatizadas | ✅ | 69 pruebas de backend (90 % de cobertura) + prueba E2E en navegador (16 comprobaciones) |

## Prueba final obligatoria (sección 13)

Ejecutada en Chromium contra la pila completa (`apps/web/e2e/final-test.mjs`): **16/16 comprobaciones superadas**.
También se ejecuta como prueba de backend (`tests/test_harness.py`). Resultado:
- Investigación real: 13 tareas, 4 ramas de adquisición en paralelo, 29 afirmaciones recuperadas y verificadas.
- 57 citas comprobadas literalmente contra sus fuentes, cada una con su localizador de sección.
- 25 eventos con precisión explícita (`range`, `century`, `disputed`, `approximate_year`, `exact_year`).
  Por ejemplo, la fecha de P52 aparece como **discutida**, con la evidencia contraria (Nongbri 2005).
- 9 incertidumbres reconocidas y cuestiones abiertas (p. ej., qué significa «texto original»).
- Ilustraciones vectoriales originales, cada una con su procedencia y marcada como esquema, no como reproducción.
- Mapa esquemático con 18 lugares.
- Misiones completables, con calificación en el servidor y explicaciones. El progreso persiste al recargar.
- Modo académico sin gamificación. Narración opcional mediante la síntesis de voz del navegador (gratuita).
- Exportación en Markdown y JSON con las referencias.
- El propietario audita los costes y la traza en `/admin` y aprueba la publicación; después la experiencia es visible para visitantes.

Capturas: `docs/screenshots/`.

## Limitaciones honestas
1. **Corpus semilla**: 5 notas editoriales del proyecto que resumen bibliografía secundaria real (Tov, Metzger &
   Ehrman, VanderKam, Barkay et al. 2004, Nongbri 2005…). Están **pendientes de revisión por especialistas** y las
   referencias no indican números de página. La aplicación lo declara en cada experiencia.
2. **Sin red hacia fuentes externas** en el entorno de desarrollo: OpenAlex y Crossref están implementados y probados
   con respuestas simuladas, pero **no contra los servicios reales**. Los identificadores externos figuran como
   `unverified_offline`.
3. **Sin proveedor LLM integrado**: los agentes operativos son deterministas (reglas, recuperación y verificación).
   La interpretación de intención es por palabras clave. Solo el área bíblica tiene contenido; las otras 19 áreas
   muestran «sin contenido verificado» en lugar de texto generado.
4. **Embeddings léxicos** (hashing), no neuronales: la búsqueda semántica tiene ruido. Hay un umbral para
   mitigarlo y el contrato `Embedder` permite cambiar de modelo.
5. **Mapa esquemático** sin cartografía base (no se dependía de teselas externas). En la zona del Levante las etiquetas se solapan.
6. Las 31 especializaciones agénticas restantes, 12 modalidades y 54 tablas están diseñadas, no implementadas.
7. Los costes de los agentes deterministas son 0 USD. El mecanismo de presupuesto está probado con costes configurados.

## Problemas encontrados y corregidos durante la fase
- Carrera entre ramas paralelas al avanzar de fase → transición atómica bajo bloqueo de fila.
- Carrera en el control de presupuesto con ramas paralelas → reserva atómica (prueba dedicada).
- El panel renderizaba una pestaña con los datos de otra → los datos quedan asociados a su pestaña.
- La búsqueda textual exigía todos los términos → combinación OR con ranking por cobertura.

## Siguientes pasos
Ver `ROADMAP.md`.
