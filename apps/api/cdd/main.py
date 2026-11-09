"""Punto de entrada FastAPI de Ciencia de Dios."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1 import admin, router
from .config import get_settings
from .db import check_connection, close_pool, get_pool
from .harness.engine import Worker


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
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


app = FastAPI(title="Ciencia de Dios API", version="0.1.0", lifespan=lifespan,
              description="HARNESS SUPRA · Evidence Engine · Experience OS — la evidencia antes que la conclusión.")
app.add_middleware(CORSMiddleware, allow_origins=get_settings().cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def security_headers(request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    return resp


app.include_router(router)
app.include_router(admin)
