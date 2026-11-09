# Seguridad

## Implementado y probado
- **RLS en las 22 tablas** (`enable` + `force`), con políticas para visitante, usuario, editor y propietario. El backend
  ejecuta las consultas de usuario con `set local role authenticated|anon` y `request.jwt.claims`, igual que PostgREST.
  Así la API no puede saltarse RLS por error.
- **Sin credenciales administrativas en el cliente**: el frontend solo usa `NEXT_PUBLIC_SUPABASE_ANON_KEY`. La conexión
  privilegiada vive solo en el backend (workers).
- **Escalada de privilegios**: los roles viven en `user_roles`; solo el propietario los modifica (probado).
- **JWT**: verificación HS256 (secreto del proyecto Supabase) o JWKS (claves asimétricas). Los tokens falsificados se
  rechazan (probado). Los tokens de desarrollo quedan desactivados fuera de `development`/`test`.
- **Inyección de instrucciones desde documentos**: `security/injection.py` marca los fragmentos sospechosos
  (`injection_risk`). El bibliotecario los excluye como evidencia (probado con un documento malicioso). Los agentes
  actuales son deterministas: nunca ejecutan herramientas a partir del contenido. `wrap_untrusted()` delimita los
  documentos para un futuro uso con LLM.
- **Herramientas autorizadas por agente**: `AgentContext.tool()` deniega y audita cualquier herramienta no concedida
  (probado).
- **Citas fabricadas**: un trigger SQL impide registrar evidencias cuyo fragmento no esté en la fuente.
- **Licencias**: no se ingieren documentos cuya licencia no permite extractos (`LicenseBlocked`); si la licencia no permite
  el texto completo, se truncan los fragmentos al mostrarlos.
- **Gasto**: reserva atómica, límites por ejecución, agente, usuario, proveedor y globales (diario y mensual),
  y aprobación explícita del propietario por encima del umbral.
- **Cabeceras**: CSP, `X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy` (web y API). CORS restringido por configuración.
- **Secretos**: solo por variables de entorno; el panel muestra pistas enmascaradas (`mask_secret`).

## Riesgos conocidos y pendientes
- El stream SSE acepta `?access_token=` porque `EventSource` no envía cabeceras: el token puede quedar en registros
  del proxy. Pendiente: tokens de corta duración específicos para el stream.
- Sin limitación de tasa (rate limiting) por IP o usuario en la API. Pendiente antes de producción.
- El clasificador de inyección es heurístico (expresiones regulares) y tiene falsos negativos.
- No se ha hecho una auditoría externa ni pruebas de penetración.
