"""Plain dataclasses shared across the harness."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Task:
    id: str
    prompt: str
    tools: list[str] = field(default_factory=list)
    graders: list[dict[str, Any]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    result: str
    is_error: bool = False
    latency_s: float = 0.0


@dataclass
class Trajectory:
    """Everything the agent did for one trial, not just its final answer."""

    final_answer: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    steps: int = 0  # model turns taken
    input_tokens: int = 0
    output_tokens: int = 0
    latency_s: float = 0.0
    error: str | None = None


@dataclass
class GraderResult:
    type: str
    passed: bool
    detail: str = ""


@dataclass
class TrialResult:
    task_id: str
    trial: int
    passed: bool
    grader_results: list[GraderResult]
    trajectory: Trajectory
    tags: list[str] = field(default_factory=list)
    expected_tools: list[str] = field(default_factory=list)
