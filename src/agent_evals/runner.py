"""Load suites, run agents, and grade trajectories."""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

import yaml

from .agents import Agent
from .graders import grade, validate_spec
from .models import Task, TrialResult, Trajectory
from .tools import build_registry


@dataclass
class Suite:
    name: str
    tasks: list[Task]


def load_suite(path: str | Path) -> Suite:
    data = yaml.safe_load(Path(path).read_text())
    if not isinstance(data, dict) or "tasks" not in data:
        raise ValueError("suite file must be a mapping with a 'tasks' list")
    tasks: list[Task] = []
    seen: set[str] = set()
    for raw in data["tasks"]:
        task = Task(
            id=raw["id"],
            prompt=raw["prompt"],
            tools=raw.get("tools", []),
            graders=raw.get("graders", []),
            tags=raw.get("tags", []),
        )
        if task.id in seen:
            raise ValueError(f"duplicate task id {task.id!r}")
        seen.add(task.id)
        if not task.graders:
            raise ValueError(f"task {task.id!r} has no graders")
        for spec in task.graders:
            validate_spec(spec)
        build_registry(task.tools)  # validates tool names
        tasks.append(task)
    return Suite(name=data.get("name", Path(path).stem), tasks=tasks)


def run_suite(suite: Suite, agent: Agent, trials: int = 1) -> list[TrialResult]:
    results: list[TrialResult] = []
    for task in suite.tasks:
        registry = build_registry(task.tools)
        expected_tools = [g["tool"] for g in task.graders if g["type"] == "tool_called"]
        for trial in range(trials):
            start = time.perf_counter()
            try:
                traj = agent.run(task, registry)
            except Exception as exc:  # an agent crash is a failed trial, not a failed run
                traj = Trajectory(error=f"{type(exc).__name__}: {exc}")
            traj.latency_s = time.perf_counter() - start
            grader_results = [grade(spec, traj) for spec in task.graders]
            results.append(
                TrialResult(
                    task_id=task.id,
                    trial=trial,
                    passed=all(g.passed for g in grader_results) and traj.error is None,
                    grader_results=grader_results,
                    trajectory=traj,
                    tags=task.tags,
                    expected_tools=expected_tools,
                )
            )
    return results
