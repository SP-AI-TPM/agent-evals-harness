"""Exercise the ClaudeAgent loop with a fake client. No network, no API key.

This verifies our loop logic (tool dispatch, message threading, token
accounting, step limit). It does NOT verify behavior against the live API.
"""

from types import SimpleNamespace as NS

from agent_evals.agents import ClaudeAgent
from agent_evals.models import Task
from agent_evals.tools import build_registry


def text(t):
    return NS(type="text", text=t)


def tool_use(id_, name, input_):
    return NS(type="tool_use", id=id_, name=name, input=input_)


def resp(content, stop_reason, i=10, o=5):
    return NS(content=content, stop_reason=stop_reason, usage=NS(input_tokens=i, output_tokens=o))


class FakeClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []
        self.messages = self  # client.messages.create(...)

    def create(self, **kwargs):
        # snapshot messages: the agent mutates the same list across turns
        self.calls.append({**kwargs, "messages": list(kwargs["messages"])})
        return self._responses.pop(0)


TASK = Task(id="t", prompt="What is 17 + 25?", tools=["calculator"])


def test_tool_use_loop_and_accounting():
    client = FakeClient(
        [
            resp([tool_use("tu_1", "calculator", {"expression": "17 + 25"})], "tool_use", 10, 5),
            resp([text("It is 42.")], "end_turn", 20, 7),
        ]
    )
    traj = ClaudeAgent(model="test-model", client=client).run(TASK, build_registry(["calculator"]))

    assert traj.final_answer == "It is 42."
    assert traj.steps == 2
    assert (traj.input_tokens, traj.output_tokens) == (30, 12)
    assert [c.name for c in traj.tool_calls] == ["calculator"]
    assert traj.tool_calls[0].result == "42"
    assert traj.error is None

    # the second request must carry the assistant tool_use turn and our tool_result
    second = client.calls[1]["messages"]
    assert second[-1]["content"][0]["type"] == "tool_result"
    assert second[-1]["content"][0]["tool_use_id"] == "tu_1"
    assert second[-1]["content"][0]["content"] == "42"
    # tool definitions were sent on every request
    assert client.calls[0]["tools"][0]["name"] == "calculator"


def test_tool_error_is_reported_back_to_the_model():
    client = FakeClient(
        [
            resp([tool_use("tu_1", "calculator", {"expression": "__import__('os')"})], "tool_use"),
            resp([text("Sorry, I could not compute that.")], "end_turn"),
        ]
    )
    traj = ClaudeAgent(model="m", client=client).run(TASK, build_registry(["calculator"]))
    assert traj.tool_calls[0].is_error
    assert client.calls[1]["messages"][-1]["content"][0]["is_error"] is True


def test_step_limit_sets_error():
    looping = [resp([tool_use(f"tu_{i}", "calculator", {"expression": "1 + 1"})], "tool_use") for i in range(5)]
    traj = ClaudeAgent(model="m", max_steps=3, client=FakeClient(looping)).run(TASK, build_registry(["calculator"]))
    assert traj.steps == 3
    assert "max_steps" in traj.error
    assert traj.final_answer == ""
