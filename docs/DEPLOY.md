# Publicar CIENCIA Y DIOS en internet

| Pieza | Dónde | Coste |
|---|---|---|
| Base de datos y cuentas | **Supabase** (ya configurado) | Plan gratuito |
| API + HARNESS (FastAPI, worker en segundo plano) | **Render** (Docker, `render.yaml`) | Plan gratuito (se duerme tras 15 min sin uso) o *Starter* |
| Web (Next.js) | **Vercel** | Plan gratuito |

Las claves secretas nunca se suben al repositorio: las pegas tú en Render y en Vercel.

---

## 1. API en Render (unos 10 minutos)

### 1.1 Genera las variables desde tu PC
Desde `apps\api` (usa tu `.env`, que ya funciona con Supabase y Gemini):
```bash
.\.venv\Scripts\python -m cdd.render_env --web-url https://PON-AQUI-TU-WEB.vercel.app
```
Crea `apps\api\.env.render` con los valores de **producción**: sin accesos de desarrollo y con CORS para tu web. Este archivo no se sube a git.
Si todavía no tienes la URL de Vercel, usa una provisional y la cambias en el paso 3.

### 1.2 Crea el servicio con el Blueprint
1. Entra en **https://dashboard.render.com** e inicia sesión con **GitHub**.
2. **New** → **Blueprint** → elige el repositorio **CiDios**. Si no aparece, pulsa *Configure GitHub* y dale acceso.
3. Render lee `render.yaml` y propone el servicio **ciencia-y-dios-api**. Te pedirá los valores marcados como secretos: cópialos de `apps\api\.env.render`.
   (Alternativa: crea el Blueprint dejando los secretos vacíos y después, en el servicio, **Environment** → **Add from .env** → pega todo el contenido de `.env.render` → **Save changes**.)
4. **Apply**. La primera construcción tarda unos 3–6 minutos.

### 1.3 Comprueba
Abre `https://ciencia-y-dios-api.onrender.com/v1/health` (Render te muestra la URL exacta). Debe responder:
```json
{"status":"ok","env":"production","api_version":"v1","worker":"running"}
```
Si falla, mira **Logs** en Render. Los mensajes de la API explican la causa (contraseña de la base, etc.).

> **Plan gratuito:** el servicio se duerme tras 15 minutos sin visitas y tarda unos 30–60 s en despertar. Las investigaciones
> en cola continúan al despertar. Para que esté siempre activo, cambia `plan: free` por `plan: starter` en Render.

---

## 2. Web en Vercel (unos 5 minutos)
1. **https://vercel.com** → inicia sesión con GitHub → **Add New…** → **Project** → importa **CiDios**.
2. **Root Directory**: `apps/web`. Vercel detecta Next.js solo.
3. **Environment Variables**:
   ```
   NEXT_PUBLIC_API_URL=https://ciencia-y-dios-api.onrender.com
   NEXT_PUBLIC_SUPABASE_URL=https://udoobbjkpazhycvnnonh.supabase.co
   NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...   (la misma de tu .env.local)
   NEXT_PUBLIC_DEV_AUTH=false
   ```
4. **Deploy**. Obtendrás una URL como `https://ciencia-y-dios.vercel.app`.

---

## 3. Conecta las piezas
1. **Render** → servicio → **Environment** → `CDD_CORS_ORIGINS` = `["https://TU-WEB.vercel.app"]` → **Save** (se reinicia solo).
2. **Supabase** → **Authentication** → **URL Configuration**:
   - **Site URL**: `https://TU-WEB.vercel.app`
   - **Redirect URLs**: añade `https://TU-WEB.vercel.app/**` (y conserva `http://localhost:3000/**` para desarrollo).
3. Abre tu web, **Entrar** → **Soy nuevo** → crea la cuenta (o entra con la que ya tienes) y comprueba **Centro de control → Sistema**.

## 4. Correo de registro (recomendado)
El correo gratuito de Supabase envía pocos mensajes por hora. Para usuarios reales, configura un SMTP propio en
Supabase → **Project Settings** → **Authentication** → **SMTP Settings** (por ejemplo Resend, Brevo o SendGrid).

## 5. Búsqueda semántica con Gemini (opcional, recomendado)
En tu `apps\api\.env` y en Render: `CDD_EMBEDDINGS_PROVIDER=gemini`. Después, una sola vez desde tu PC:
```bash
.\.venv\Scripts\python -m cdd.reembed --dry-run
```
```bash
.\.venv\Scripts\python -m cdd.reembed
```
Recalcula los vectores de la biblioteca con Gemini. El primer comando muestra cuántos fragmentos y el coste aproximado.

## Actualizaciones
Cada `git push` a la rama `claude/serene-bohr-znv5a8` vuelve a publicar la API en Render (`autoDeploy`) y la web en Vercel.
Si una actualización trae migraciones nuevas, aplícalas desde tu PC con `python -m cdd.migrate`.
