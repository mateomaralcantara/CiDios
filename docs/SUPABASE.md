# Conectar CIENCIA Y DIOS a Supabase

Guía completa para pasar de la base local (Docker) a un proyecto de Supabase propio.
Los nombres de los menús del panel de Supabase pueden variar ligeramente según la versión.

## 0. Qué necesitas de Supabase y dónde va cada cosa

| Dato | Dónde se obtiene en Supabase | Dónde se pone | ¿Secreto? |
|---|---|---|---|
| **URL del proyecto** (`https://<ref>.supabase.co`) | Project Settings → Data API (o botón **Connect**) | `apps/web/.env.local` → `NEXT_PUBLIC_SUPABASE_URL` · `apps/api/.env` → `CDD_SUPABASE_URL` | No |
| **Clave pública** (*Publishable key* `sb_publishable_…` o *anon key* `eyJ…`) | Project Settings → API Keys | `apps/web/.env.local` → `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` | No (va al navegador; RLS protege los datos) |
| **Cadena de conexión** a Postgres (*Session pooler*) | Botón **Connect** → Connection string → Session pooler | `apps/api/.env` → `CDD_DATABASE_URL` | **Sí** (contiene la contraseña) |
| **Verificación de tokens**: URL JWKS **o** *Legacy JWT secret* | Project Settings → JWT Keys | `apps/api/.env` → `CDD_SUPABASE_JWKS_URL` **o** `CDD_SUPABASE_JWT_SECRET` | El JWT secret **sí** |
| *Secret key* / *service_role* | Project Settings → API Keys | **En ninguna parte.** Este proyecto no la necesita | **Sí, máximo** |

> La API del proyecto se conecta directamente a Postgres y aplica RLS por usuario, así que **no necesita la
> service_role key**. Nunca la pongas en una variable `NEXT_PUBLIC_…` ni en el repositorio.

## 1. Crear el proyecto

1. En https://supabase.com crea un proyecto nuevo (por ejemplo `ciencia-y-dios`). Guarda la **contraseña de la base**.
2. Elige la región más cercana a donde desplegarás la API.

## 2. Configurar la API (`apps/api/.env`)

```bash
cd C:\Users\martin\Desktop\VSC\BestS\cidios-app\apps\api
```
```bash
copy ..\..\.env.example .env
```
Edita `apps\api\.env` y deja estas líneas (con tus datos):

```ini
CDD_ENV=development
CDD_DATABASE_URL=postgresql://postgres.<ref>:<contraseña>@aws-0-<región>.pooler.supabase.com:5432/postgres?sslmode=require
CDD_SUPABASE_URL=https://<ref>.supabase.co
CDD_SUPABASE_JWKS_URL=https://<ref>.supabase.co/auth/v1/.well-known/jwks.json
# Si tu proyecto usa el secreto JWT clásico, usa esta línea en lugar de la anterior:
# CDD_SUPABASE_JWT_SECRET=<Legacy JWT secret>
CDD_DEV_AUTH=false
CDD_CORS_ORIGINS=["http://localhost:3000"]
```

- **Forma más segura de poner la contraseña:** desde `apps\api`, ejecuta `.\.venv\Scripts\python -m cdd.set_database_url`.
  Te pide la contraseña sin mostrarla, la codifica, **prueba la conexión** y solo si funciona la guarda en `.env`.
- Usa el **Session pooler** (puerto 5432). La conexión *Direct* puede ser solo IPv6, y muchas redes no la admiten.
  Si usas el *Transaction pooler* (puerto 6543), la API desactiva automáticamente las sentencias preparadas.
- Si la contraseña tiene caracteres especiales (`@ # / ? :`), escríbelos codificados: `@` → `%40`, `#` → `%23`.

## 3. Crear las tablas en Supabase

Hay dos formas equivalentes; elige **una**.

### Opción A — Desde el panel de Supabase (sin terminal)
1. Abre `supabase/setup_supabase.sql` del repositorio y copia **todo** su contenido.
2. En Supabase: **SQL Editor** → **New query** → pega → **Run**.
3. Debe terminar sin errores (puede mostrar avisos «NOTICE», son normales). En **Table Editor** verás las 22 tablas.

El script corre en una sola transacción: si algo falla, no se crea nada. También deja registradas las migraciones,
así que `python -m cdd.migrate` y `supabase db push` las darán por aplicadas. Si lo ejecutas dos veces, se detiene
con un mensaje sin tocar nada.

### Opción B — Desde tu PC con la API configurada (paso 2)
```bash
.\.venv\Scripts\python -m cdd.migrate --status
```
```bash
.\.venv\Scripts\python -m cdd.migrate
```
Lo aplicado se registra en `supabase_migrations.schema_migrations`, la misma tabla que usa la Supabase CLI
(`supabase link --project-ref <ref>` + `supabase db push` es otra alternativa equivalente).

Con cualquiera de las dos opciones se crean las 22 tablas, las políticas RLS, la búsqueda híbrida y el disparador que
crea el perfil de cada usuario nuevo. Para futuras migraciones usa la opción B, que solo aplica lo pendiente.

> **No** uses `python -m cdd.dbreset` con Supabase: ese comando borra la base y es solo para la base local
> (se niega a ejecutarse con una URL de Supabase).

## 4. Cargar el catálogo inicial

```bash
.\.venv\Scripts\python -m cdd.seed
```
Carga los 40 agentes, las 20 áreas, las políticas de presupuesto y el corpus verificado. **Sin** `--dev-users`:
en Supabase los usuarios se registran de verdad.

## 5. Configurar Supabase Auth

1. Authentication → URL Configuration:
   - **Site URL**: `http://localhost:3000` (y, al desplegar, la URL de Vercel).
   - **Redirect URLs**: añade las mismas.
2. Authentication → Sign In / Providers → **Email**: déjalo activado. La confirmación por correo está recomendada.

## 6. Configurar la web (`apps/web/.env.local`)

```bash
cd C:\Users\martin\Desktop\VSC\BestS\cidios-app\apps\web
```
```bash
copy .env.example .env.local
```
Edita `apps\web\.env.local`:
```ini
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://<ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=sb_publishable_...   # o la anon key
NEXT_PUBLIC_DEV_AUTH=false
```

## 7. Arrancar, registrarte y hacerte propietario

1. Arranca la API (`.\.venv\Scripts\uvicorn cdd.main:app --port 8000`) y la web (`npm run dev`).
2. En http://localhost:3000 → **Entrar** → escribe tu correo y contraseña → **Crear cuenta** → confirma el correo.
3. Asígnate el rol de propietario (desde `apps\api`):
   ```bash
   .\.venv\Scripts\python -m cdd.make_owner tu@correo.com
   ```
4. Cierra sesión y vuelve a entrar: verás **Centro de control** en el menú.

## 8. Comprobar que todo está bien

```bash
.\.venv\Scripts\python -m cdd.doctor
```
Revisa la configuración, la conexión, las extensiones, las migraciones, que RLS esté activo en las 22 tablas y que un
visitante **no** pueda leer tablas privadas (lo prueba de verdad). También comprueba los datos iniciales, el
propietario y el acceso al JWKS. Cada ✗ indica el comando que lo arregla.

## 9. Documentación de la API de cada tabla

- **`docs/API-TABLAS.md`**: para cada tabla, sus columnas, claves, políticas RLS (quién puede leer o escribir y qué
  filas), permisos y ejemplos con `curl` y `supabase-js`.
- **`packages/contracts/database.types.ts`**: tipos TypeScript compatibles con `createClient<Database>(…)`.

Ambos se generan desde la base real; regéneralos después de cada migración:
```bash
.\.venv\Scripts\python -m cdd.export_schema
```

## Problemas frecuentes

| Mensaje | Causa | Solución |
|---|---|---|
| `password authentication failed` | Contraseña o usuario incorrectos en `CDD_DATABASE_URL` | Copia de nuevo la cadena del *Session pooler*; el usuario es `postgres.<ref>` |
| `No existe auth.uid()` al migrar | La URL apunta a una base que no es de Supabase | Revisa `CDD_DATABASE_URL` |
| La web dice «Token inválido» | La API no tiene `CDD_SUPABASE_JWKS_URL` / `CDD_SUPABASE_JWT_SECRET`, o no coincide con el proyecto | Copia el valor de Project Settings → JWT Keys y reinicia la API |
| No aparece «Centro de control» | Tu usuario no es propietario | `python -m cdd.make_owner tu@correo.com` y vuelve a entrar |
| `cdd.doctor` avisa de `FORCE RLS` | Falta la migración de compatibilidad | `python -m cdd.migrate` |
