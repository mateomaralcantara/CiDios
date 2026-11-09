"""Máquina de estados del HARNESS."""
from __future__ import annotations

MAIN_CHAIN = ["CREATED", "AUTHORIZED", "PLANNED", "ACQUIRING", "ANALYZING", "CROSS_EXAMINING",
              "VERIFYING", "PACKAGING", "RENDERING", "QA", "READY", "PUBLISHED"]
INTERRUPTIONS = {"PAUSED", "AWAITING_APPROVAL", "BUDGET_EXHAUSTED", "LICENSE_BLOCKED"}
TERMINAL = {"PUBLISHED", "FAILED", "CANCELLED"}
ALL_STATES = set(MAIN_CHAIN) | INTERRUPTIONS | TERMINAL | {"PARTIAL"}


class InvalidTransition(Exception):
    pass


def can_transition(current: str, new: str, previous: str | None = None) -> bool:
    if current in TERMINAL or new not in ALL_STATES or current == new:
        return False
    if new in ("FAILED", "CANCELLED"):
        return True
    if current == "PARTIAL":
        return False
    if new in INTERRUPTIONS or new == "PARTIAL":
        return current in MAIN_CHAIN and current not in ("READY",)
    if new == "PUBLISHED":
        return current == "READY"
    if current in INTERRUPTIONS:
        # Reanudación: se vuelve a la fase interrumpida o a una posterior, nunca hacia atrás.
        anchor = previous if previous in MAIN_CHAIN else "AUTHORIZED"
        return new in MAIN_CHAIN and MAIN_CHAIN.index(new) >= MAIN_CHAIN.index(anchor) and new != "PUBLISHED"
    if current in MAIN_CHAIN and new in MAIN_CHAIN:
        return MAIN_CHAIN.index(new) > MAIN_CHAIN.index(current)
    return False


def assert_transition(current: str, new: str, previous: str | None = None) -> None:
    if not can_transition(current, new, previous):
        raise InvalidTransition(f"Transición no permitida: {current} → {new}")
