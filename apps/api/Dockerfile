# API de CIENCIA Y DIOS (FastAPI + HARNESS). Construir desde la RAÍZ del repositorio:
#   docker build -f apps/api/Dockerfile -t cdd-api .
FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 \
    CDD_REPO_ROOT=/srv/cdd CDD_CORPUS_DIR=/srv/cdd/corpus PORT=8000
WORKDIR /srv/cdd/apps/api

COPY apps/api/pyproject.toml ./
COPY apps/api/cdd ./cdd
RUN pip install --upgrade pip && pip install .

# Datos que la API necesita en tiempo de ejecución: corpus inicial y migraciones (para cdd.seed / cdd.migrate)
COPY corpus /srv/cdd/corpus
COPY supabase/migrations /srv/cdd/supabase/migrations
COPY supabase/tests/00_local_supabase_shim.sql /srv/cdd/supabase/tests/00_local_supabase_shim.sql

RUN useradd --create-home --uid 10001 app && chown -R app /srv/cdd
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s CMD python -c "import urllib.request,os;urllib.request.urlopen(f'http://127.0.0.1:{os.environ.get(\"PORT\",\"8000\")}/v1/health',timeout=4)"
# Render asigna el puerto en $PORT. Un único proceso: API + worker del HARNESS en segundo plano.
CMD ["sh", "-c", "uvicorn cdd.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips='*'"]
