import pytest

from agent_evals.tools import build_registry, calculator, lookup, safe_eval


def test_calculator_basic():
    assert calculator("17 + 25") == "42"
    assert calculator("144 / 12") == "12"
    assert calculator("7 / 2") == "3.5"
    assert calculator("-3 * 4") == "-12"


@pytest.mark.parametrize("bad", ["__import__('os').system('ls')", "2 ** 9999", "abs(-1)", "x + 1", "True + 1"])
def test_safe_eval_rejects_everything_but_arithmetic(bad):
    with pytest.raises((ValueError, SyntaxError)):
        safe_eval(bad)


def test_lookup():
    assert lookup("capital:France") == "Paris"
    assert lookup("capital:atlantis") == "NOT_FOUND"


def test_registry_rejects_unknown_tool():
    with pytest.raises(ValueError, match="unknown tool"):
        build_registry(["calculator", "teleporter"])


def test_anthropic_tool_shape():
    tool = build_registry(["calculator"]).get("calculator")
    d = tool.to_anthropic()
    assert set(d) == {"name", "description", "input_schema"}
    assert d["input_schema"]["required"] == ["expression"]
