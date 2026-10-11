import json
from pathlib import Path

from agent_evals.cli import main
from agent_evals.gate import evaluate_gate

SUITE = str(Path(__file__).parent.parent / "suites" / "demo_suite.yaml")


def m(success=1.0, tool=1.0, p95=1.0, cost=None, per_task=None):
    return {
        "task_success_rate": success,
        "tool_call_accuracy": tool,
        "latency_p95_s": p95,
        "cost_usd": cost,
        "per_task_pass_rate": per_task or {},
    }


def test_gate_passes_when_equal():
    assert evaluate_gate(m(), m()) == []


def test_gate_fails_on_success_drop_and_names_tasks():
    v = evaluate_gate(m(per_task={"a": 1.0}), m(success=0.9, per_task={"a": 0.0}))
    assert any("task_success_rate" in x for x in v)
    assert any("'a' regressed" in x for x in v)


def test_gate_tolerance_allows_small_drop():
    assert evaluate_gate(m(), m(success=0.95), max_success_drop=0.05) == []


def test_gate_tool_accuracy_latency_cost():
    v = evaluate_gate(
        m(cost=1.0), m(tool=0.5, p95=2.0, cost=2.0), max_latency_increase_pct=50, max_cost_increase_pct=50
    )
    assert any("tool_call_accuracy" in x for x in v)
    assert any("latency_p95" in x for x in v)
    assert any("cost" in x for x in v)


def test_gate_ignores_missing_optional_metrics():
    assert evaluate_gate(m(tool=None), m(tool=None)) == []


def test_cli_end_to_end_pass_and_fail(tmp_path, capsys):
    base, good, bad = (str(tmp_path / f"{n}.json") for n in ("base", "good", "bad"))
    report = str(tmp_path / "report.md")

    assert main(["run", "--suite", SUITE, "--agent", "mock-reference", "--out", base, "--report", report]) == 0
    assert main(["run", "--suite", SUITE, "--agent", "mock-reference", "--out", good]) == 0
    assert main(["run", "--suite", SUITE, "--agent", "mock-flawed", "--out", bad]) == 0

    assert main(["gate", "--baseline", base, "--candidate", good]) == 0
    assert "GATE PASSED" in capsys.readouterr().out
    assert main(["gate", "--baseline", base, "--candidate", bad]) == 1
    assert "GATE FAILED" in capsys.readouterr().out

    text = Path(report).read_text()
    assert "# Eval report: demo-suite" in text and "Task success rate" in text
    assert json.loads(Path(base).read_text())["metrics"]["task_success_rate"] == 1.0
