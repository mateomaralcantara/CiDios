"""Contexto de ejecución de un agente y pasarela de herramientas autorizadas."""
from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..db import service_tx, user_tx


class ToolNotAuthorized(Exception):
    pass


class NoEvidence(Exception):
    """La biblioteca no contiene evidencia pertinente: la ejecución termina en PARTIAL sin generar contenido."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.details = details or {}


@dataclass
class AgentContext:
    run_id: str
    owner_id: str
    task_key: str
    agent_code: str
    allowed_tools: list[str]
    task_input: dict[str, Any]
    deps: dict[str, dict[str, Any]]          # salidas de las tareas de las que depende
    run_plan: dict[str, Any]
    cost_usd: float = 0.0
    warnings: list[str] = field(default_factory=list)

    def owner_claims(self) -> dict[str, Any]:
        return {"sub": self.owner_id, "role": "authenticated"}

    def tool(self, name: str) -> None:
        """Comprueba la autorización y registra el uso de una herramienta (auditoría)."""
        if name not in self.allowed_tools:
            log_event(self.run_id, "tool_denied", f"{self.agent_code} intentó usar {name} sin autorización",
                      level="audit", task_key=self.task_key, data={"tool": name})
            raise ToolNotAuthorized(f"El agente {self.agent_code} no está autorizado a usar {name}")
        log_event(self.run_id, "tool_call", f"{self.agent_code} → {name}", level="debug", task_key=self.task_key,
                  data={"tool": name})

    def as_owner(self):
        """Lecturas con las credenciales RLS del dueño de la investigación (nunca ve datos privados ajenos)."""
        return user_tx(self.owner_claims())

    def log(self, message: str, level: str = "info", data: dict | None = None) -> None:
        log_event(self.run_id, "agent_log", message, level=level, task_key=self.task_key, data=data or {})


def log_event(run_id: str, event_type: str, message: str, *, level: str = "info", task_key: str | None = None,
              data: dict | None = None) -> None:
    with service_tx() as conn:
        conn.execute(
            "insert into public.harness_events (run_id, task_key, level, event_type, message, data) values (%s,%s,%s,%s,%s,%s)",
            (run_id, task_key, level, event_type, message, json.dumps(data or {}, default=str)))


AgentFn = Callable[[AgentContext], dict[str, Any]]
