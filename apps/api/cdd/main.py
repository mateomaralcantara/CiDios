"""Punto de entrada FastAPI de Ciencia y Dios."""
from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.v1 import admin, review, router
from .config import get_settings
from .db import check_connection, close_pool, get_pool
from .harness.engine import Worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
STARTED_AT = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    logging.getLogger("cdd").info("CORS permitido para: %s", ", ".join(s.cors_origins) or "(ninguno)")
    check_connection()   # si falla, la API no arranca y explica por qué
    get_pool()
    worker = None
    if s.run_worker_in_api:
        worker = Worker(s.worker_poll_interval_s)
        worker.start()
    yield
    if worker:
        worker.stop()
        worker.join(timeout=5)
    close_pool()


app = FastAPI(title="Ciencia y Dios API", version="0.1.0", lifespan=lifespan,
              description="HARNESS SUPRA · Evidence Engine · Experience OS — la evidencia antes que la conclusión.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])


_hits: dict[str, deque] = defaultdict(deque)


@app.middleware("http")
async def rate_limit(request, call_next):
    """Límite simple por IP (ventana deslizante de 60 s). Detrás del proxy de Render, request.client es la IP real."""
    limit = get_settings().rate_limit_per_minute
    if (limit > 0 and request.method != "OPTIONS" and request.url.path.startswith("/v1/")
            and request.url.path != "/v1/health"):
        ip = request.client.host if request.client else "?"
        now = time.monotonic()
        q = _hits[ip]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            return JSONResponse({"detail": "Demasiadas peticiones. Espera un minuto e inténtalo de nuevo."}, status_code=429,
                                headers={"Retry-After": "60"})
        q.append(now)
        if len(_hits) > 50_000:      # evita crecer sin límite
            _hits.clear()
    return await call_next(request)


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


app.include_router(router)
app.include_router(admin)
app.include_router(review)
