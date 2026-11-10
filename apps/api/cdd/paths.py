"""Rutas del proyecto, válidas tanto en el repositorio como dentro del contenedor Docker de Render.

Nunca falla al importar: primero usa las variables de entorno y, si no existen, sube por las carpetas
hasta encontrar la raíz del repositorio (la que contiene supabase/ o corpus/).
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path


@lru_cache
def repo_root() -> Path:
    env = os.environ.get("CDD_REPO_ROOT")
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "supabase" / "migrations").is_dir() or (parent / "corpus").is_dir():
            return parent
    return Path.cwd()


def corpus_dir() -> Path:
    return Path(os.environ.get("CDD_CORPUS_DIR") or repo_root() / "corpus")


def migrations_dir() -> Path:
    return repo_root() / "supabase" / "migrations"
