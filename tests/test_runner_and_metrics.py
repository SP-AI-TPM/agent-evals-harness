from pathlib import Path

import pytest

from agent_evals.agents import MockAgent
from agent_evals.metrics import compute_metrics, percentile
from agent_evals.runner import load_suite, run_suite

SUITE = Path(__file__).parent.parent / "suites" / "demo_suite.yaml"


def test_reference_agent_passes_everything():
    results = run_suite(load_suite(SUITE), MockAgent("reference"))
    assert all(r.passed for r in results), [r.task_id for r in results if not r.passed]


def test_flawed_agent_fails_on_math_process_and_hallucination():
    results = run_suite(load_suite(SUITE), MockAgent("flawed"))
    failed = {r.task_id for r in results if not r.passed}
    # wrong arithmetic
    assert {"add", "multiply", "divide"} <= failed
    # right answer from memory but skipped the tool: caught by trajectory grading
    assert "capital-france" in failed
    # hallucinated entity
    assert "capital-atlantis" in failed


def test_metrics_for_reference_and_flawed():
    suite = load_suite(SUITE)
    good = compute_metrics(run_suite(suite, MockAgent("reference")))
    bad = compute_metrics(run_suite(suite, MockAgent("flawed")))
    assert good["task_success_rate"] == 1.0
    assert good["tool_call_accuracy"] == 1.0
    assert bad["task_success_rate"] < 0.2
    assert bad["tool_call_accuracy"] == 0.0
    assert good["cost_usd"] is None  # no prices supplied, none invented


def test_cost_uses_only_caller_supplied_prices():
    results = run_suite(load_suite(SUITE), MockAgent("reference"))
    m = compute_metrics(results, price_in_per_mtok=1.0, price_out_per_mtok=2.0)
    expected = m["input_tokens"] / 1e6 * 1.0 + m["output_tokens"] / 1e6 * 2.0
    assert m["cost_usd"] == pytest.approx(expected)


def test_trials_and_consistency():
    suite = load_suite(SUITE)
    results = run_suite(suite, MockAgent("reference"), trials=3)
    assert len(results) == 3 * len(suite.tasks)
    m = compute_metrics(results)
    assert m["trials"] == len(results)
    assert m["consistency_rate"] == 1.0


def test_crashing_agent_is_a_failed_trial_not_a_crashed_run():
    class Boom:
        def run(self, task, registry):
            raise RuntimeError("kaput")

    results = run_suite(load_suite(SUITE), Boom())
    assert all(not r.passed for r in results)
    assert all("kaput" in r.trajectory.error for r in results)
    assert compute_metrics(results)["error_rate"] == 1.0


def test_percentile():
    assert percentile([], 95) == 0.0
    assert percentile([1, 2, 3, 4], 50) == 2
    assert percentile([1, 2, 3, 4], 95) == 4


def test_load_suite_validation(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("tasks:\n  - {id: a, prompt: hi, graders: [{type: nope}]}\n")
    with pytest.raises(ValueError, match="unknown grader"):
        load_suite(bad)
    dup = tmp_path / "dup.yaml"
    dup.write_text("tasks:\n  - {id: a, prompt: hi, graders: [{type: no_error}]}\n  - {id: a, prompt: hi, graders: [{type: no_error}]}\n")
    with pytest.raises(ValueError, match="duplicate"):
        load_suite(dup)
    nog = tmp_path / "nog.yaml"
    nog.write_text("tasks:\n  - {id: a, prompt: hi}\n")
    with pytest.raises(ValueError, match="no graders"):
        load_suite(nog)
