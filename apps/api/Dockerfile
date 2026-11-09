FROM python:3.13-slim
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY apps/api/pyproject.toml ./
COPY apps/api/cdd ./cdd
COPY corpus /corpus
ENV CDD_CORPUS_DIR=/corpus PYTHONUNBUFFERED=1
RUN uv pip install --system --no-cache .
RUN useradd -m app && chown -R app /app
USER app
EXPOSE 8000
# API: uvicorn; worker separado: `python -m cdd.worker`
CMD ["uvicorn", "cdd.main:app", "--host", "0.0.0.0", "--port", "8000"]
