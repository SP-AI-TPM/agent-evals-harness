"""Aggregate trial results into the numbers a launch review actually looks at."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any

from .models import TrialResult


def percentile(values: list[float], pct: float) -> float:
    """Nearest-rank percentile. Returns 0.0 for empty input."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(pct / 100 * len(ordered)))
    return ordered[rank - 1]


def compute_metrics(
    results: list[TrialResult],
    price_in_per_mtok: float | None = None,
    price_out_per_mtok: float | None = None,
) -> dict[str, Any]:
    """Prices are caller-supplied. The harness does not hardcode any provider's rates."""
    n = len(results)
    if n == 0:
        raise ValueError("no results to aggregate")

    passed = sum(r.passed for r in results)
    errors = sum(r.trajectory.error is not None for r in results)

    with_tools = [r for r in results if r.expected_tools]
    tool_ok = sum(
        all(any(c.name == t for c in r.trajectory.tool_calls) for t in r.expected_tools) for r in with_tools
    )

    by_task: dict[str, list[bool]] = defaultdict(list)
    for r in results:
        by_task[r.task_id].append(r.passed)
    # Consistency: fraction of tasks where every trial passed. Matters when trials > 1.
    consistent = sum(all(v) for v in by_task.values())

    in_tok = sum(r.trajectory.input_tokens for r in results)
    out_tok = sum(r.trajectory.output_tokens for r in results)
    latencies = [r.trajectory.latency_s for r in results]

    metrics: dict[str, Any] = {
        "trials": n,
        "tasks": len(by_task),
        "task_success_rate": passed / n,
        "consistency_rate": consistent / len(by_task),
        "tool_call_accuracy": (tool_ok / len(with_tools)) if with_tools else None,
        "error_rate": errors / n,
        "avg_steps": sum(r.trajectory.steps for r in results) / n,
        "avg_tool_calls": sum(len(r.trajectory.tool_calls) for r in results) / n,
        "input_tokens": in_tok,
        "output_tokens": out_tok,
        "latency_p50_s": percentile(latencies, 50),
        "latency_p95_s": percentile(latencies, 95),
        "cost_usd": None,
    }
    if price_in_per_mtok is not None and price_out_per_mtok is not None:
        metrics["cost_usd"] = in_tok / 1e6 * price_in_per_mtok + out_tok / 1e6 * price_out_per_mtok

    per_task = {tid: sum(v) / len(v) for tid, v in by_task.items()}
    metrics["per_task_pass_rate"] = per_task
    return metrics
