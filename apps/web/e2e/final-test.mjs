// Prueba final obligatoria (sección 13) ejecutada en un navegador real contra la pila completa.
// Uso: WEB_URL=http://localhost:3000 API_URL=http://localhost:8000 SHOTS=./e2e/shots node e2e/final-test.mjs
import { createRequire } from "node:module";
import fs from "node:fs";
const require = createRequire(import.meta.url);
let playwright;
try { playwright = require("playwright"); } catch { playwright = require("/opt/node-tools/node_modules/playwright"); }

const WEB = process.env.WEB_URL ?? "http://localhost:3000";
const API = process.env.API_URL ?? "http://localhost:8000";
const SHOTS = process.env.SHOTS ?? "e2e/shots";
fs.mkdirSync(SHOTS, { recursive: true });
const results = [];
const check = (name, ok, detail = "") => { results.push({ name, ok: !!ok, detail }); console.log(`${ok ? "✓" : "✗"} ${name}${detail ? " — " + detail : ""}`); };

const PROMPT = "Investiga la historia de la transmisión de los textos bíblicos desde sus testimonios antiguos hasta las ediciones modernas. Muéstrame las evidencias arqueológicas y textuales, las posiciones académicas relevantes, las dataciones conocidas y las incertidumbres. Convierte la investigación en una línea de tiempo ilustrada y gamificada, con mapas, fuentes consultables, misiones pedagógicas, preguntas interactivas y narración opcional";

const browser = await playwright.chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1360, height: 900 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();
page.on("pageerror", (e) => console.log("pageerror:", e.message));

// 1. Usuario entra y lanza la investigación desde la UI
await page.goto(`${WEB}/entrar`);
await page.getByTestId("dev-user").click();
await page.waitForURL("**/investigar");
await page.getByTestId("prompt").fill(PROMPT);
await page.getByTestId("launch").click();
await page.waitForURL("**/ejecuciones/**");
const runId = page.url().split("/ejecuciones/")[1].split("?")[0];
await page.getByTestId("run-state").filter({ hasText: "READY" }).waitFor({ timeout: 60000 });
check("Existe una investigación real ejecutada por el HARNESS", true, `run ${runId}`);
await page.screenshot({ path: `${SHOTS}/1-ejecucion.png`, fullPage: true });
const token = await page.evaluate(() => localStorage.getItem("cdd.dev-session"));
const run = await (await fetch(`${API}/v1/runs/${runId}`, { headers: { Authorization: `Bearer ${token}` } })).json();
check("Ejecución registrada (tareas, eventos, checkpoints)", run.tasks.length >= 14 && run.tasks.every((t) => t.status === "succeeded") && run.checkpoints.length === run.tasks.length);
check("Costes consultables", run.costs.length >= 14, `${run.costs.length} asientos en el libro de costes`);

// 2. Experiencia
await page.getByTestId("open-experience").click();
await page.waitForURL("**/experiencias/**");
const expId = page.url().split("/experiencias/")[1];
await page.getByTestId("timeline-event").first().waitFor();
const exp = await (await fetch(`${API}/v1/experiences/${expId}`, { headers: { Authorization: `Bearer ${token}` } })).json();
const spec = exp.experience_spec, packet = exp.knowledge_packet;
check("Citas comprobables (todas verificadas literalmente)", packet.claims.every((c) => c.evidence.length && c.evidence.every((e) => e.verification === "fragment_verified")), `${packet.claims.reduce((n, c) => n + c.evidence.length, 0)} citas`);
check("Eventos con fechas y grado de precisión", spec.events.every((e) => e.date_label && e.precision), `${spec.events.length} eventos; precisiones: ${[...new Set(spec.events.map((e) => e.precision))].join(", ")}`);
check("Imágenes con procedencia", spec.events.every((e) => e.illustration.provenance.notice && e.illustration.provenance.license));
check("Incertidumbres reconocidas", packet.uncertainties.length > 0 && packet.claims.some((c) => c.category === "open_question"), `${packet.uncertainties.length} incertidumbres`);
await page.screenshot({ path: `${SHOTS}/2-linea-de-tiempo.png`, fullPage: false });

// fuentes consultables
await page.getByTestId("open-sources").first().click();
await page.getByTestId("sources-panel").waitFor();
check("Fuentes consultables desde la experiencia", await page.getByTestId("sources-panel").locator("blockquote").count() > 0);
await page.screenshot({ path: `${SHOTS}/3-fuentes.png` });
await page.keyboard.press("Escape");
await page.getByRole("button", { name: "Cerrar" }).click();

// etapa 2 bloqueada
check("Etapas bloqueadas hasta completar la misión", await page.getByTestId("stage-1").isDisabled());

// 3. Misión 1: primero un intento fallido, luego correcto
const m1 = spec.stages[0].mission;
const qs = page.getByTestId("question");
for (let i = 0; i < m1.questions.length; i++) {
  const q = m1.questions[i];
  await qs.nth(i).locator("input[type=radio]").nth((q.correct_index + 1) % q.options.length).check();
}
await page.getByTestId("submit-mission").click();
await page.getByTestId("mission-result").waitFor();
check("Las preguntas se califican y explican", (await page.getByTestId("mission-result").innerText()).includes("Aún no") && await page.getByTestId("feedback").count() === m1.questions.length);
for (let i = 0; i < m1.questions.length; i++) await qs.nth(i).locator("input[type=radio]").nth(m1.questions[i].correct_index).check();
await page.getByTestId("submit-mission").click();
await page.getByTestId("mission-result").filter({ hasText: "superada" }).waitFor();
await page.getByTestId("stage-1").isEnabled();
check("Las misiones pueden completarse y desbloquean etapas", await page.getByTestId("stage-1").isEnabled());
await page.screenshot({ path: `${SHOTS}/4-mision.png`, fullPage: true });

// 4. Progreso persistente tras recargar
await page.reload();
await page.getByTestId("progress").waitFor();
const prog = await page.getByTestId("progress").innerText();
check("El progreso se guarda", prog.includes("1/5") && await page.getByTestId("stage-1").isEnabled(), prog);

// 5. Modo académico sin gamificación
await page.getByTestId("mode-academic").click();
check("Modo académico sin gamificación", await page.getByTestId("stage-4").isEnabled() && await page.getByTestId("mission").count() === 0);
await page.getByTestId("stage-4").click();
await page.screenshot({ path: `${SHOTS}/5-academico.png`, fullPage: false });

// 6. Mapa
check("Mapa con lugares", await page.locator("svg[aria-label^='Mapa esquemático'] circle").count() >= 10);

// 7. Propietario audita y publica
await page.getByRole("button", { name: "Salir" }).click();
await page.goto(`${WEB}/entrar`);
await page.getByTestId("dev-owner").click();
await page.waitForURL("**/investigar");
await page.goto(`${WEB}/admin`);
await page.getByTestId("tab-ejecuciones").click();
await page.getByRole("link", { name: /Investiga la historia/ }).first().waitFor();
check("El panel administrativo permite auditar el proceso", true);
await page.getByTestId("tab-costes").click();
await page.getByText("Por investigación").waitFor();
await page.screenshot({ path: `${SHOTS}/6-admin-costes.png`, fullPage: true });
await page.goto(`${WEB}/ejecuciones/${runId}`);
await page.getByTestId("publish").click();
await page.getByTestId("run-state").filter({ hasText: "PUBLISHED" }).waitFor();
const anon = await fetch(`${API}/v1/experiences/${expId}`);
check("Publicación aprobada por el propietario, visible para visitantes", anon.status === 200);
await page.goto(`${WEB}/admin`);
await page.getByText("Ejecuciones por estado").waitFor();
await page.screenshot({ path: `${SHOTS}/7-admin.png`, fullPage: true });

await browser.close();
fs.writeFileSync(`${SHOTS}/results.json`, JSON.stringify({ runId, expId, results }, null, 2));
const failed = results.filter((r) => !r.ok);
console.log(failed.length ? `\n${failed.length} comprobaciones fallidas` : `\nPrueba final superada: ${results.length}/${results.length}`);
process.exit(failed.length ? 1 : 0);
