"""Command line interface: `agent-evals run` and `agent-evals gate`."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .agents import Agent, ClaudeAgent, MockAgent
from .gate import evaluate_gate
from .metrics import compute_metrics
from .report import render_report
from .runner import load_suite, run_suite


def _make_agent(name: str, model: str | None, max_steps: int) -> Agent:
    if name == "mock-reference":
        return MockAgent("reference")
    if name == "mock-flawed":
        return MockAgent("flawed")
    if name == "claude":
        if not model:
            raise SystemExit("--model is required for --agent claude")
        return ClaudeAgent(model=model, max_steps=max_steps)
    raise SystemExit(f"unknown agent {name!r}")


def _cmd_run(args: argparse.Namespace) -> int:
    suite = load_suite(args.suite)
    agent = _make_agent(args.agent, args.model, args.max_steps)
    results = run_suite(suite, agent, trials=args.trials)
    metrics = compute_metrics(results, args.price_in, args.price_out)
    label = args.agent + (f" ({args.model})" if args.model else "")

    payload = {"suite": suite.name, "agent": label, "metrics": metrics}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if args.report:
        Path(args.report).write_text(render_report(suite.name, label, results, metrics))
    print(
        f"{suite.name}: success {metrics['task_success_rate']:.1%} "
        f"({sum(r.passed for r in results)}/{len(results)} trials) -> {out}"
    )
    return 0


def _cmd_gate(args: argparse.Namespace) -> int:
    baseline = json.loads(Path(args.baseline).read_text())["metrics"]
    candidate = json.loads(Path(args.candidate).read_text())["metrics"]
    violations = evaluate_gate(
        baseline,
        candidate,
        max_success_drop=args.max_success_drop,
        max_tool_accuracy_drop=args.max_tool_accuracy_drop,
        max_latency_increase_pct=args.max_latency_increase_pct,
        max_cost_increase_pct=args.max_cost_increase_pct,
    )
    if violations:
        print("GATE FAILED")
        for v in violations:
            print(f"  - {v}")
        return 1
    print("GATE PASSED")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agent-evals", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a suite against an agent")
    run.add_argument("--suite", required=True)
    run.add_argument("--agent", default="mock-reference", choices=["mock-reference", "mock-flawed", "claude"])
    run.add_argument("--model", help="model id, required for --agent claude")
    run.add_argument("--trials", type=int, default=1)
    run.add_argument("--max-steps", type=int, default=8)
    run.add_argument("--price-in", type=float, help="USD per million input tokens (you supply this)")
    run.add_argument("--price-out", type=float, help="USD per million output tokens (you supply this)")
    run.add_argument("--out", default="results.json")
    run.add_argument("--report", help="optional markdown report path")
    run.set_defaults(func=_cmd_run)

    gate = sub.add_parser("gate", help="compare candidate results to a baseline")
    gate.add_argument("--baseline", required=True)
    gate.add_argument("--candidate", required=True)
    gate.add_argument("--max-success-drop", type=float, default=0.0)
    gate.add_argument("--max-tool-accuracy-drop", type=float, default=0.0)
    gate.add_argument("--max-latency-increase-pct", type=float)
    gate.add_argument("--max-cost-increase-pct", type=float)
    gate.set_defaults(func=_cmd_gate)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
