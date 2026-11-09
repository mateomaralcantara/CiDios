# Hoja de ruta

## Fase 2: fuentes y modelos reales
- Crear el proyecto Supabase de producción y desplegar en staging (Vercel + servicio para API/worker).
- Activar OpenAlex y Crossref con salida de red; resolver identificadores (`identifier_check=resolved`).
- Conectores: PubMed/Europe PMC, arXiv, SEP (solo metadatos y enlaces), NASA ADS, colecciones de manuscritos.
- Agente #4 (Enrutador de modelos) + proveedor LLM para la extracción de afirmaciones *propuestas* (`draft`): siempre con
  verificación literal del agente #27 y revisión humana antes de publicarse.
- Embeddings neuronales (misma dimensión o migración del índice).
- Revisión experta del corpus semilla (`review_status=reviewed`) con flujo `review_requests`/`expert_reviews`.

## Fase 3: contraste y calidad
- Agentes #23 (lógica), #24 (escéptico metodológico), #25 (defensor de hipótesis), #28 (auditor de imparcialidad).
- Evaluación continua (`evaluation_runs`): exactitud de citas, cobertura, sesgo y accesibilidad (#39).
- Limitación de tasa y tokens de corta duración para SSE.

## Fase 4: Experience OS ampliado
- Modalidades: atlas con cartografía base, grafo de conocimiento, debate estructurado, infografía, informe académico.
- Multimedia con procedencia (`media_*`) y generación de pago **solo con aprobación** del propietario (#36).
- Cursos y lecciones interactivas (dominio Educación).

## Fase 5: áreas científicas y filosóficas
- Corpus verificados para cosmología, evolución, neurociencia, filosofía de la religión y religiones del mundo, con los
  agentes #13–#22.
