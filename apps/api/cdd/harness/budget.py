"""Custodio de presupuesto: límites por investigación, usuario, agente, proveedor y globales (diario/mensual)."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from psycopg import Connection


@dataclass
class BudgetDecision:
    allow: bool
    reason: str
    requires_approval: bool = False
    limits: dict[str, Any] | None = None


def _policy(conn: Connection, scope: str, ref: str, period: str) -> dict | None:
    return conn.execute(
        """select * from public.budget_policies where active and scope=%s and scope_ref in (%s,'*') and period=%s
           order by (scope_ref = '*') limit 1""", (scope, ref, period)).fetchone()


def _spent(conn: Connection, where: str, args: tuple, period: str) -> Decimal:
    window = {"daily": "1 day", "monthly": "1 month"}.get(period)
    sql = f"select coalesce(sum(amount_usd),0) as s from public.cost_ledger where kind='actual' and {where}"
    if window:
        sql += f" and created_at > now() - interval '{window}'"
    return conn.execute(sql, args).fetchone()["s"]


def check(conn: Connection, *, run: dict, agent: dict, estimate: Decimal, provider: str = "local") -> BudgetDecision:
    estimate = Decimal(estimate)
    limits: dict[str, Any] = {}
    run_spent = Decimal(run["spent_usd"])
    if run_spent + estimate > Decimal(run["budget_usd"]):
        return BudgetDecision(False, f"Presupuesto de la investigación agotado ({run_spent}+{estimate} > {run['budget_usd']})")
    agent_spent = _spent(conn, "run_id=%s and agent_code=%s", (run["id"], agent["code"]), "per_run")
    if agent_spent + estimate > Decimal(agent["max_cost_per_run_usd"]):
        return BudgetDecision(False, f"Tope del agente {agent['code']} por investigación alcanzado")
    for period in ("daily", "monthly"):
        p = _policy(conn, "user", str(run["owner_id"]), period)
        if p:
            s = _spent(conn, "user_id=%s", (run["owner_id"],), period)
            limits[f"user_{period}"] = {"limit": str(p["limit_usd"]), "spent": str(s)}
            if s + estimate > p["limit_usd"]:
                return BudgetDecision(False, f"Límite {period} del usuario alcanzado", limits=limits)
        g = _policy(conn, "global", "*", period)
        if g:
            s = _spent(conn, "true", (), period)
            limits[f"global_{period}"] = {"limit": str(g["limit_usd"]), "spent": str(s)}
            if s + estimate > g["limit_usd"]:
                return BudgetDecision(False, f"Presupuesto global {period} agotado", limits=limits)
        pr = _policy(conn, "provider", provider, period)
        if pr:
            s = _spent(conn, "provider=%s", (provider,), period)
            if s + estimate > pr["limit_usd"]:
                return BudgetDecision(False, f"Límite {period} del proveedor {provider} alcanzado", limits=limits)
    return BudgetDecision(True, "Dentro de presupuesto", limits=limits)


def reserve(conn: Connection, *, run_id: str, agent: dict, estimate: Decimal, provider: str = "local") -> BudgetDecision:
    """Comprueba y reserva el gasto de forma atómica (bloqueo de fila de la ejecución).

    Evita que ramas paralelas del DAG superen juntas el presupuesto.
    """
    run = conn.execute("select * from public.harness_runs where id=%s for update", (run_id,)).fetchone()
    decision = check(conn, run=run, agent=agent, estimate=estimate, provider=provider)
    if decision.allow and estimate:
        conn.execute("update public.harness_runs set spent_usd = spent_usd + %s where id=%s", (estimate, run_id))
    return decision


def approval_threshold(conn: Connection) -> Decimal:
    p = _policy(conn, "investigation", "*", "per_run")
    return Decimal(p["auto_approve_below_usd"]) if p else Decimal("0.50")


def record(conn: Connection, *, run_id: str, user_id: str, agent_code: str | None, kind: str, amount: Decimal,
           provider: str = "local", model: str = "deterministic", input_tokens: int = 0, output_tokens: int = 0,
           cache_hit: bool = False, note: str = "", apply_to_run: bool = True) -> None:
    conn.execute(
        """insert into public.cost_ledger (run_id, user_id, agent_code, provider, model, kind, input_tokens, output_tokens,
             amount_usd, cache_hit, note) values (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (run_id, user_id, agent_code, provider, model, kind, input_tokens, output_tokens, amount, cache_hit, note))
    if kind == "actual" and apply_to_run:
        conn.execute("update public.harness_runs set spent_usd = spent_usd + %s where id = %s", (amount, run_id))
