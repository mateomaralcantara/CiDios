# Gemini + búsqueda en 3 dimensiones + HARNESS de bibliografía

## Qué hace cada pieza

| Pieza | Qué aporta | Dónde está |
|---|---|---|
| **Dimensión 1 · Textos publicados del área** | Busca obras en OpenAlex, Crossref, Europe PMC y arXiv según el área y guarda sus **resúmenes** en la biblioteca, con DOI, licencia y procedencia | Agente #8, `harness/agents/discovery.py` |
| **Dimensión 2 · Expertos del área** | Identifica autores con trayectoria en el tema (**índice h ≥ 15** en OpenAlex) e incorpora sus obras **revisadas por pares** pertinentes | Agente #8 (modo expertos) |
| **Gemini** | (a) genera consultas académicas en inglés y español; (b) el **especialista del área** (#15–#22) propone afirmaciones a partir de los fragmentos | `providers/gemini.py`, `harness/agents/extraction.py` |
| **Verificación literal** | Cada cita propuesta por Gemini debe aparecer **carácter por carácter** en el fragmento; si no, se descarta | Extracción + disparador SQL + agente #27 |
| **HARNESS de bibliografía** | COLLECT → RESOLVE (DOI en Crossref) → AUDIT (retractaciones y duplicados) → CLASSIFY (procedencia) → FORMAT (APA 7 / Chicago) → BIND (citas [n]) → REPORT (métricas de solidez) | Agente #12, `bibliography/harness.py` |

## Flujo de una investigación con Gemini

```
Pregunta
  └─ #1 Intención (área) → #2 Plan → #5 Presupuesto
       ├─ Biblioteca propia (#7, búsqueda híbrida)                  ┐
       ├─ Dimensión 1: Gemini genera consultas → repositorios → resúmenes   │ en paralelo
       └─ Dimensión 2: autores de la dimensión 1 + OpenAlex → índice h ≥ 15 → sus obras revisadas por pares
            └─ Especialista del área (Gemini): propone afirmaciones con citas literales
                 └─ verificación carácter por carácter (lo inventado se descarta)
                      └─ #26 Análisis y contraste → #27 Verificación de citas
                           └─ #12 HARNESS de bibliografía (DOI, retractaciones, APA, [n])
                                └─ KnowledgePacket (con bibliografía) → experiencia → control de calidad
```

Reglas que no cambian con Gemini:
- Gemini **nunca** escribe el texto final libremente. Solo propone afirmaciones atómicas, y cada una debe tener al menos una cita **literal** de un fragmento real.
- Las afirmaciones propuestas por la IA quedan **privadas** del autor de la investigación y **pendientes de revisión**, y se marcan como «propuesta por IA».
- Los documentos se entregan al modelo como **datos no confiables**: las instrucciones que contengan se ignoran.
- Las obras **retractadas** se excluyen. Una afirmación que solo dependía de ellas desaparece del resultado.
- Si las fuentes no permiten responder, el resultado es «sin evidencia suficiente», nunca contenido inventado.
- El gasto se mide con los **tokens reales** que informa Gemini y se registra en el libro de costes, con los mismos límites y la misma aprobación de antes.

## Instalación (Windows · PowerShell)

### 1. Consigue tu clave de Gemini
1. Entra en **https://aistudio.google.com/apikey** con tu cuenta de Google.
2. **Create API key** y copia la clave. No la pegues en ningún chat ni en el repositorio.

### 2. (Recomendado) Consigue tu clave gratuita de OpenAlex
Sin ella, la **dimensión 2 (expertos)** puede fallar, porque OpenAlex limita las peticiones sin clave.
Crea una cuenta en **https://openalex.org** y genera tu clave desde la configuración de tu cuenta.

### 3. Actualiza el proyecto
```bash
cd C:\Users\martin\Desktop\VSC\BestS\cidios-app
```
```bash
git pull
```
```bash
cd apps\api
```
```bash
.\.venv\Scripts\pip install -e ".[dev]"
```

### 4. Pon las claves en `apps\api\.env`
```bash
code C:\Users\martin\Desktop\VSC\BestS\cidios-app\apps\api\.env
```
Añade estas líneas al final, con tus claves:
```ini
CDD_GEMINI_API_KEY=tu-clave-de-gemini
CDD_GEMINI_MODEL=gemini-2.5-flash
CDD_OPENALEX_API_KEY=tu-clave-de-openalex
CDD_CONNECTORS_ENABLED=["openalex","crossref","europepmc","arxiv"]
```
Guarda con `Ctrl + S`.

### 5. Aplica la migración nueva a tu base (Supabase o local)
```bash
.\.venv\Scripts\python -m cdd.migrate
```
```bash
.\.venv\Scripts\python -m cdd.seed
```
El seed activa los nuevos agentes operativos: el descubridor bibliográfico, el auditor de bibliografía, los especialistas y el enrutador de modelos.

### 6. Prueba los servicios en vivo
```bash
.\.venv\Scripts\python -m cdd.check_external
```
Debe mostrar `✓ responde (gemini-…)` y `✓` en cada repositorio. La llamada de prueba a Gemini cuesta fracciones de céntimo.

### 6 bis. Comprueba todas las claves de una vez
```bash
powershell -ExecutionPolicy Bypass -File C:\Users\martin\Desktop\VSC\BestS\cidios-app\probar-claves.ps1
```
Prueba la base de datos, Supabase Auth, la clave pública de la web, que la web no tenga claves secretas, Gemini,
OpenAlex, los repositorios y la API. Nunca muestra una clave completa; cada ✗ indica cómo arreglarlo.

### 7. Arranca y prueba
```bash
.\.venv\Scripts\uvicorn cdd.main:app --port 8000
```
Y en otra terminal, en `apps\web`: `npm run dev`.

En **Investigar**, prueba una pregunta fuera del corpus inicial, por ejemplo:
*«Según la neurociencia, ¿qué se sabe sobre la experiencia religiosa y la conciencia?»*

En la página de la ejecución verás las tareas `acquire_published`, `acquire_experts`, `extract` y `bibliography`. En la experiencia, la sección **Bibliografía y sustento** muestra las tres dimensiones, las referencias numeradas en APA y su procedencia.

## Modelos y costes
- `CDD_GEMINI_MODEL`: `gemini-2.5-flash` (rápido y económico) o `gemini-2.5-pro` (más capaz, más caro). Si Google publica modelos nuevos, cambia el nombre aquí. `check_external` te dirá si el modelo existe para tu clave.
- Ajusta `CDD_GEMINI_INPUT_USD_PER_MTOK` y `CDD_GEMINI_OUTPUT_USD_PER_MTOK` a los precios vigentes en https://ai.google.dev/pricing. El control de presupuesto los usa.
- Una investigación típica hace 2 llamadas (consultas + extracción) con unos 20 fragmentos: del orden de céntimos con `flash`.
- Límites: por investigación (1 USD por defecto), por usuario y día, globales, y aprobación del propietario por encima de 0,50 USD. Se configuran en **Centro de control → Presupuestos**.

## Qué está probado y qué no
- ✅ Conectores **en vivo**: Crossref, Europe PMC y arXiv responden y sus obras se incorporan a la biblioteca.
- ✅ OpenAlex en vivo responde, pero sin clave rechaza por cupo; el formato se probó con respuestas simuladas.
- ✅ Cliente de Gemini, extracción, verificación literal, retractaciones, APA y costes: probados con **respuestas simuladas** de Gemini (`tests/test_gemini_dimensions.py`).
- ⚠ **No probado contra Gemini real** desde el entorno de desarrollo, porque no tiene clave: el paso 6 (`check_external`) es tu prueba en vivo.
