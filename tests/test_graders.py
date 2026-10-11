import pytest

from agent_evals.graders import grade, validate_spec
from agent_evals.models import ToolCall, Trajectory


def traj(answer="The answer is 42.", calls=None, steps=2, error=None):
    return Trajectory(final_answer=answer, tool_calls=calls or [], steps=steps, error=error)


def call(name="calculator", args=None, is_error=False):
    return ToolCall(name=name, args=args or {}, result="x", is_error=is_error)


def test_contains_is_case_insensitive():
    assert grade({"type": "contains", "value": "THE ANSWER"}, traj()).passed
    assert not grade({"type": "contains", "value": "43"}, traj()).passed


def test_not_contains():
    assert grade({"type": "not_contains", "value": "43"}, traj()).passed
    assert not grade({"type": "not_contains", "value": "42"}, traj()).passed


def test_exact_match_normalizes_case_and_edges():
    assert grade({"type": "exact_match", "value": "paris"}, traj(" Paris ")).passed
    assert not grade({"type": "exact_match", "value": "paris"}, traj("It is Paris")).passed


def test_regex():
    assert grade({"type": "regex", "pattern": r"\b42\b"}, traj()).passed
    assert not grade({"type": "regex", "pattern": r"\b43\b"}, traj()).passed


def test_tool_called_with_min():
    t = traj(calls=[call(), call()])
    assert grade({"type": "tool_called", "tool": "calculator", "min": 2}, t).passed
    assert not grade({"type": "tool_called", "tool": "calculator", "min": 3}, t).passed
    assert not grade({"type": "tool_called", "tool": "lookup"}, t).passed


def test_tool_not_called():
    assert grade({"type": "tool_not_called", "tool": "lookup"}, traj(calls=[call()])).passed
    assert not grade({"type": "tool_not_called", "tool": "calculator"}, traj(calls=[call()])).passed


def test_tool_args_ignores_case_and_whitespace():
    t = traj(calls=[call("calculator", {"expression": "17+25"})])
    assert grade({"type": "tool_args", "tool": "calculator", "args": {"expression": "17 + 25"}}, t).passed
    assert not grade({"type": "tool_args", "tool": "calculator", "args": {"expression": "1 + 1"}}, t).passed


def test_step_and_call_limits():
    t = traj(calls=[call(), call()], steps=3)
    assert grade({"type": "max_steps", "value": 3}, t).passed
    assert not grade({"type": "max_steps", "value": 2}, t).passed
    assert grade({"type": "max_tool_calls", "value": 2}, t).passed
    assert not grade({"type": "max_tool_calls", "value": 1}, t).passed


def test_no_error_catches_agent_and_tool_errors():
    assert grade({"type": "no_error"}, traj()).passed
    assert not grade({"type": "no_error"}, traj(error="boom")).passed
    assert not grade({"type": "no_error"}, traj(calls=[call(is_error=True)])).passed


def test_validation_rejects_bad_specs():
    with pytest.raises(ValueError, match="unknown grader"):
        validate_spec({"type": "nope"})
    with pytest.raises(ValueError, match="missing required"):
        validate_spec({"type": "contains"})
