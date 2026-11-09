"""Contratos versionados: KnowledgePacket → ExperienceSpec → Renderer.

El KnowledgePacket contiene afirmaciones, evidencias, perspectivas, fechas y limitaciones verificadas.
El ExperienceSpec solo REFERENCIA afirmaciones del paquete (por id); nunca las reescribe.
Los esquemas JSON exportados viven en packages/contracts/.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PACKET_VERSION = "1.0.0"
SPEC_VERSION = "1.0.0"


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DateInfo(_M):
    start: int | None = None
    end: int | None = None
    precision: str
    precision_label: str
    label: str


class Place(_M):
    name: str
    lat: float | None = None
    lon: float | None = None


class DocumentRef(_M):
    id: str
    title: str
    slug: str | None = None
    license_code: str
    review_status: str
    kind: str


class BibRef(_M):
    id: str
    slug: str
    authors: list[str]
    title: str
    container_title: str | None = None
    publisher: str | None = None
    year: int | None = None
    edition: str | None = None
    identifiers: dict[str, str] = {}
    identifier_check: str


class EvidenceItem(_M):
    id: str
    stance: Literal["supports", "challenges", "contextualizes", "qualifies"]
    fragment: str
    locator: str
    document: DocumentRef
    reference: BibRef | None = None
    verification: Literal["fragment_verified", "fragment_mismatch", "unverified", "reference_missing"]
    verification_notes: list[str] = []


class PerspectiveItem(_M):
    label: str
    tradition: str
    summary: str
    held_by: str = ""


class PacketClaim(_M):
    id: str
    slug: str
    statement: str
    statement_sha256: str
    asserted_by: str
    discipline: str
    category: str
    category_label: str
    is_event: bool
    date: DateInfo | None = None
    place: Place | None = None
    subject: str | None = None
    illustration_kind: str | None = None
    consensus_note: str = ""
    insufficient_evidence_note: str = ""
    future_research_note: str = ""
    review_status: str
    evidence: list[EvidenceItem]
    perspectives: list[PerspectiveItem] = []


class KnowledgePacket(_M):
    packet_version: str = PACKET_VERSION
    run_id: str
    question: str
    topic: str | None
    generated_at: str
    claims: list[PacketClaim]
    excluded_claims: list[dict] = []
    uncertainties: list[str] = []
    limitations: list[str] = []
    coverage: dict = {}
    sha256: str = ""


def canonical_sha256(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def packet_hash(packet: KnowledgePacket) -> str:
    return canonical_sha256(packet.model_dump(exclude={"sha256"}))


# ---------------------------------------------------------------- ExperienceSpec
class Provenance(_M):
    creator: str
    kind: Literal["schematic_illustration", "photograph", "facsimile", "map", "reconstruction"]
    license: str
    is_reconstruction: bool
    notice: str
    source_url: str | None = None


class Illustration(_M):
    kind: str
    alt: str
    provenance: Provenance


class TimelineEvent(_M):
    claim_id: str
    title: str
    sort_key: float
    date_label: str
    precision: str
    stage_id: str
    narration: str  # debe coincidir literalmente con la afirmación del paquete
    illustration: Illustration
    place_name: str | None = None


class Question(_M):
    id: str
    claim_id: str
    kind: Literal["dating", "place", "epistemic_category", "evidence"]
    prompt: str
    options: list[str] = Field(min_length=2)
    correct_index: int
    explanation: str


class Mission(_M):
    id: str
    title: str
    objective: str
    questions: list[Question] = Field(min_length=1)
    pass_threshold: float = 0.5


class Stage(_M):
    id: str
    index: int
    title: str
    range_label: str
    intro: str
    event_claim_ids: list[str]
    mission: Mission | None = None


class MapPoint(_M):
    name: str
    lat: float
    lon: float
    claim_ids: list[str]


class MapSpec(_M):
    kind: Literal["schematic"] = "schematic"
    notice: str
    bounds: dict[str, float]
    points: list[MapPoint]


class ArticleSection(_M):
    heading: str
    intro: str = ""
    claim_ids: list[str]


class ExperienceSpec(_M):
    spec_version: str = SPEC_VERSION
    modality: Literal["article", "comparison_matrix", "timeline", "gamified_timeline"]
    title: str
    language: str = "es"
    packet_sha256: str
    gamified: bool = False
    academic_mode_available: bool = True
    narration: dict = {}
    stages: list[Stage] = []
    events: list[TimelineEvent] = []
    map: MapSpec | None = None
    sections: list[ArticleSection] = []
    notices: list[str] = []
