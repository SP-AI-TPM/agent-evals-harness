"""Render a markdown report from results and metrics."""

from __future__ import annotations

from typing import Any

from .models import TrialResult


def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.1%}"


def render_report(suite_name: str, agent_label: str, results: list[TrialResult], metrics: dict[str, Any]) -> str:
    cost_value = metrics["cost_usd"]
    cost = "n/a (no prices given)" if cost_value is None else f"{cost_value:.4f}"
    lines = [
        f"# Eval report: {suite_name}",
        "",
        f"Agent: `{agent_label}`  |  trials: {metrics['trials']}  |  tasks: {metrics['tasks']}",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Task success rate | {_pct(metrics['task_success_rate'])} |",
        f"| Consistency (all trials pass) | {_pct(metrics['consistency_rate'])} |",
        f"| Tool-call accuracy | {_pct(metrics['tool_call_accuracy'])} |",
        f"| Error rate | {_pct(metrics['error_rate'])} |",
        f"| Avg steps / tool calls | {metrics['avg_steps']:.2f} / {metrics['avg_tool_calls']:.2f} |",
        f"| Tokens in / out | {metrics['input_tokens']} / {metrics['output_tokens']} |",
        f"| Latency p50 / p95 | {metrics['latency_p50_s'] * 1000:.1f} ms / {metrics['latency_p95_s'] * 1000:.1f} ms |",
        f"| Cost (USD) | {cost} |",
        "",
        "## Per-task pass rate",
        "",
        "| Task | Pass rate |",
        "|---|---|",
    ]
    for tid, rate in metrics["per_task_pass_rate"].items():
        lines.append(f"| {tid} | {rate:.0%} |")

    failures = [r for r in results if not r.passed]
    lines += ["", "## Failures", ""]
    if not failures:
        lines.append("None.")
    for r in failures:
        lines.append(f"### {r.task_id} (trial {r.trial})")
        lines.append(f"- Final answer: {r.trajectory.final_answer!r}")
        if r.trajectory.error:
            lines.append(f"- Error: {r.trajectory.error}")
        for g in r.grader_results:
            if not g.passed:
                lines.append(f"- FAILED `{g.type}`: {g.detail}")
        lines.append("")
    return "\n".join(lines) + "\n"
