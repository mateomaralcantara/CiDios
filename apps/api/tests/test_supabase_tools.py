"""Herramientas de Supabase: migraciones, documentación de tablas y diagnóstico."""
from __future__ import annotations

import psycopg
import pytest

from cdd import doctor, export_schema, migrate

from .conftest import TEST_DB


@pytest.fixture(scope="module")
def supa_url():
    """Base vacía con lo que Supabase proporciona (roles + auth) pero sin migraciones."""
    from cdd.paths import repo_root
    base, _, _ = TEST_DB.rpartition("/")
    url = f"{base}/cdd_supa_tool_test"
    with psycopg.connect(f"{base}/postgres", autocommit=True) as c:
        c.execute("drop database if exists cdd_supa_tool_test with (force)")
        c.execute("create database cdd_supa_tool_test")
    with psycopg.connect(url, autocommit=True) as c:
        c.execute((repo_root() / "supabase/tests/00_local_supabase_shim.sql").read_text(encoding="utf-8"))
    return url


def test_migrate_refuses_non_supabase_database():
    base, _, _ = TEST_DB.rpartition("/")
    with psycopg.connect(f"{base}/postgres", autocommit=True) as c:
        c.execute("drop database if exists cdd_bare_test with (force)")
        c.execute("create database cdd_bare_test")
    assert migrate.run(f"{base}/cdd_bare_test") == 2


def test_migrate_applies_once_and_records_like_supabase_cli(supa_url, capsys):
    assert migrate.run(supa_url, status_only=True) == 0
    assert "pendiente" in capsys.readouterr().out
    assert migrate.run(supa_url) == 0
    assert migrate.run(supa_url) == 0
    assert "Nada que aplicar" in capsys.readouterr().out
    with psycopg.connect(supa_url) as c:
        versions = [r[0] for r in c.execute("select version from supabase_migrations.schema_migrations order by 1")]
        forced = c.execute("""select count(*) from pg_class where relnamespace='public'::regnamespace
                              and relkind='r' and relforcerowsecurity""").fetchone()[0]
    assert versions == [v for v, _, _ in migrate.migration_files()]
    assert forced == 0


def test_export_schema_documents_every_table(supa_url, tmp_path, monkeypatch):
    monkeypatch.setattr(export_schema, "repo_root", lambda: tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "packages" / "contracts").mkdir(parents=True)
    export_schema.main(supa_url)
    md = (tmp_path / "docs" / "API-TABLAS.md").read_text(encoding="utf-8")
    ts = (tmp_path / "packages" / "contracts" / "database.types.ts").read_text(encoding="utf-8")
    for t in doctor.TABLES:
        assert f"## {t}" in md and f"      {t}: {{" in ts
    assert "hybrid_search" in ts and 'epistemic_category: "empirical_fact"' in ts


def test_doctor_passes_on_seeded_database(capsys):
    assert doctor.run() == 0
    out = capsys.readouterr().out
    assert "Un visitante no puede leer tablas privadas" in out and "✗" not in out


def test_sql_editor_bundle_is_up_to_date():
    """supabase/setup_supabase.sql debe regenerarse tras cada migración (python -m cdd.migrate --bundle)."""
    assert migrate.bundle_path().read_text(encoding="utf-8") == migrate.bundle_sql()


def test_imports_work_inside_render_container(tmp_path):
    """En Docker el código vive en /app/cdd: importar la API no debe depender de la estructura del repositorio."""
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    import cdd
    app = tmp_path / "app"
    shutil.copytree(Path(cdd.__file__).parent, app / "cdd", ignore=shutil.ignore_patterns("__pycache__"))
    code = ("import pathlib, cdd.paths as p; "
            "pathlib.Path.parents.__class__  # noqa\n"
            "from cdd import main, seed, migrate, dbreset, export_schema; print('ok', p.corpus_dir())")
    env = {"PATH": "/usr/bin:/bin", "CDD_CORPUS_DIR": "/corpus", "CDD_REPO_ROOT": "/repo"}
    r = subprocess.run([sys.executable, "-c", code], cwd=app, env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-800:]
    assert "ok /corpus" in r.stdout
