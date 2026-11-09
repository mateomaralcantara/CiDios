"""El validador detecta cualquier alteración del conocimiento por parte del renderizador."""
from __future__ import annotations

import copy

import pytest

from cdd.db import service_tx
from cdd.harness import engine
from cdd.harness.agents.quality import validate

from .conftest import principal


@pytest.fixture(scope="module")
def artifacts():
    r = engine.create_investigation(principal("user"), "Línea de tiempo gamificada de los códices bíblicos", force_new=True)
    assert engine.process_run(r["run_id"]) == "READY"
    with service_tx() as c:
        e = c.execute("select knowledge_packet, experience_spec from public.experiences where run_id=%s", (r["run_id"],)).fetchone()
    return e["knowledge_packet"], e["experience_spec"]


def failed(checks):
    return {c["check"] for c in checks if not c["passed"]}


def test_clean_artifacts_pass(artifacts):
    assert failed(validate(*artifacts)) == set()


def test_altered_statement_detected(artifacts):
    p, s = copy.deepcopy(artifacts)
    s["events"][0]["narration"] = "El papiro fue escrito por el propio autor."
    assert "statements_unaltered" in failed(validate(p, s))


def test_tampered_packet_detected(artifacts):
    p, s = copy.deepcopy(artifacts)
    p["claims"][0]["statement"] = "Certeza inventada."
    assert "packet_integrity" in failed(validate(p, s))


def test_unknown_claim_detected(artifacts):
    p, s = copy.deepcopy(artifacts)
    s["stages"][0]["event_claim_ids"].append("00000000-0000-0000-0000-000000000000")
    assert "references_only_packet_claims" in failed(validate(p, s))


def test_altered_date_detected(artifacts):
    p, s = copy.deepcopy(artifacts)
    s["events"][0]["date_label"] = "año 33 exacto"
    assert "dates_match_packet" in failed(validate(p, s))


def test_unsolvable_mission_detected(artifacts):
    p, s = copy.deepcopy(artifacts)
    s["stages"][0]["mission"]["questions"][0]["correct_index"] = 99
    assert "missions_completable" in failed(validate(p, s))
