"""Regression gate: compare a candidate run against a baseline and decide ship / no-ship."""

from __future__ import annotations

from typing import Any


def evaluate_gate(
    baseline: dict[str, Any],
    candidate: dict[str, Any],
    max_success_drop: float = 0.0,
    max_tool_accuracy_drop: float = 0.0,
    max_latency_increase_pct: float | None = None,
    max_cost_increase_pct: float | None = None,
) -> list[str]:
    """Return a list of violations. Empty list means the gate passes."""
    violations: list[str] = []

    drop = baseline["task_success_rate"] - candidate["task_success_rate"]
    if drop > max_success_drop + 1e-9:
        violations.append(
            f"task_success_rate fell {drop:.1%} "
            f"({baseline['task_success_rate']:.1%} -> {candidate['task_success_rate']:.1%}), "
            f"allowed {max_success_drop:.1%}"
        )

    b_tool, c_tool = baseline.get("tool_call_accuracy"), candidate.get("tool_call_accuracy")
    if b_tool is not None and c_tool is not None:
        tool_drop = b_tool - c_tool
        if tool_drop > max_tool_accuracy_drop + 1e-9:
            violations.append(
                f"tool_call_accuracy fell {tool_drop:.1%} ({b_tool:.1%} -> {c_tool:.1%}), "
                f"allowed {max_tool_accuracy_drop:.1%}"
            )

    if max_latency_increase_pct is not None and baseline["latency_p95_s"] > 0:
        pct = (candidate["latency_p95_s"] / baseline["latency_p95_s"] - 1) * 100
        if pct > max_latency_increase_pct:
            violations.append(f"latency_p95 rose {pct:.1f}%, allowed {max_latency_increase_pct:.1f}%")

    b_cost, c_cost = baseline.get("cost_usd"), candidate.get("cost_usd")
    if max_cost_increase_pct is not None and b_cost and c_cost is not None:
        pct = (c_cost / b_cost - 1) * 100
        if pct > max_cost_increase_pct:
            violations.append(f"cost rose {pct:.1f}%, allowed {max_cost_increase_pct:.1f}%")

    # Name individual tasks that regressed, so the failure is actionable.
    for tid, b_rate in baseline.get("per_task_pass_rate", {}).items():
        c_rate = candidate.get("per_task_pass_rate", {}).get(tid)
        if c_rate is not None and c_rate < b_rate:
            violations.append(f"task {tid!r} regressed ({b_rate:.0%} -> {c_rate:.0%})")
    return violations
