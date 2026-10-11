"""Deterministic graders that score a whole trajectory.

Each grader is a dict in the suite YAML: {type: <name>, ...params}.
LLM-as-judge grading is intentionally out of scope here; see the sibling
llm-judge-lab project.
"""

from __future__ import annotations

import re
from typing import Any, Callable

from .models import GraderResult, Trajectory


def _norm(text: Any) -> str:
    return re.sub(r"\s+", "", str(text)).lower()


def _contains(spec: dict, t: Trajectory) -> GraderResult:
    value = str(spec["value"])
    ok = value.lower() in t.final_answer.lower()
    return GraderResult("contains", ok, f"expected {value!r} in answer")


def _not_contains(spec: dict, t: Trajectory) -> GraderResult:
    value = str(spec["value"])
    ok = value.lower() not in t.final_answer.lower()
    return GraderResult("not_contains", ok, f"expected {value!r} absent from answer")


def _exact_match(spec: dict, t: Trajectory) -> GraderResult:
    ok = t.final_answer.strip().lower() == str(spec["value"]).strip().lower()
    return GraderResult("exact_match", ok, f"expected exactly {spec['value']!r}")


def _regex(spec: dict, t: Trajectory) -> GraderResult:
    ok = re.search(spec["pattern"], t.final_answer, re.IGNORECASE) is not None
    return GraderResult("regex", ok, f"pattern {spec['pattern']!r}")


def _tool_called(spec: dict, t: Trajectory) -> GraderResult:
    count = sum(1 for c in t.tool_calls if c.name == spec["tool"])
    ok = count >= int(spec.get("min", 1))
    return GraderResult("tool_called", ok, f"{spec['tool']} called {count}x (min {spec.get('min', 1)})")


def _tool_not_called(spec: dict, t: Trajectory) -> GraderResult:
    count = sum(1 for c in t.tool_calls if c.name == spec["tool"])
    return GraderResult("tool_not_called", count == 0, f"{spec['tool']} called {count}x")


def _tool_args(spec: dict, t: Trajectory) -> GraderResult:
    """Pass if some call to `tool` has args that include every expected key/value.

    String values are compared ignoring case and whitespace.
    """
    expected = spec["args"]
    for call in t.tool_calls:
        if call.name != spec["tool"]:
            continue
        if all(k in call.args and _norm(call.args[k]) == _norm(v) for k, v in expected.items()):
            return GraderResult("tool_args", True, f"{spec['tool']} called with expected args")
    return GraderResult("tool_args", False, f"no {spec['tool']} call matched args {expected}")


def _max_steps(spec: dict, t: Trajectory) -> GraderResult:
    limit = int(spec["value"])
    return GraderResult("max_steps", t.steps <= limit, f"{t.steps} steps (limit {limit})")


def _max_tool_calls(spec: dict, t: Trajectory) -> GraderResult:
    limit = int(spec["value"])
    return GraderResult("max_tool_calls", len(t.tool_calls) <= limit, f"{len(t.tool_calls)} calls (limit {limit})")


def _no_error(spec: dict, t: Trajectory) -> GraderResult:
    bad = t.error is not None or any(c.is_error for c in t.tool_calls)
    return GraderResult("no_error", not bad, t.error or "no agent or tool errors")


GRADERS: dict[str, Callable[[dict, Trajectory], GraderResult]] = {
    "contains": _contains,
    "not_contains": _not_contains,
    "exact_match": _exact_match,
    "regex": _regex,
    "tool_called": _tool_called,
    "tool_not_called": _tool_not_called,
    "tool_args": _tool_args,
    "max_steps": _max_steps,
    "max_tool_calls": _max_tool_calls,
    "no_error": _no_error,
}

_REQUIRED = {
    "contains": ["value"],
    "not_contains": ["value"],
    "exact_match": ["value"],
    "regex": ["pattern"],
    "tool_called": ["tool"],
    "tool_not_called": ["tool"],
    "tool_args": ["tool", "args"],
    "max_steps": ["value"],
    "max_tool_calls": ["value"],
    "no_error": [],
}


def validate_spec(spec: dict) -> None:
    """Fail fast at suite-load time, not mid-run."""
    gtype = spec.get("type")
    if gtype not in GRADERS:
        raise ValueError(f"unknown grader type {gtype!r}. Available: {sorted(GRADERS)}")
    missing = [k for k in _REQUIRED[gtype] if k not in spec]
    if missing:
        raise ValueError(f"grader {gtype!r} is missing required field(s): {missing}")


def grade(spec: dict, trajectory: Trajectory) -> GraderResult:
    validate_spec(spec)
    return GRADERS[spec["type"]](spec, trajectory)
