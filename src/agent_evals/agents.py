"""Agents under test.

Every agent implements `run(task, registry) -> Trajectory`.

- MockAgent: deterministic and offline. For tests, CI, and demonstrating the
  harness. Its numbers say nothing about any real model.
- ClaudeAgent: a plain tool-use loop over the Anthropic Messages API.
"""

from __future__ import annotations

import re
from typing import Any, Protocol

from .models import Task, ToolCall, Trajectory
from .tools import Registry


class Agent(Protocol):
    def run(self, task: Task, registry: Registry) -> Trajectory: ...


def _call_tool(registry: Registry, traj: Trajectory, name: str, args: dict[str, Any]) -> str:
    tool = registry.get(name)
    if tool is None:
        out, is_err = f"error: unknown tool {name}", True
    else:
        try:
            out, is_err = str(tool.fn(**args)), False
        except Exception as exc:  # tool failures are data for the agent, not crashes
            out, is_err = f"error: {exc}", True
    traj.tool_calls.append(ToolCall(name=name, args=args, result=out, is_error=is_err))
    return out


_ARITH = re.compile(r"(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)")
_CAPITAL = re.compile(r"capital of ([A-Za-z ]+?)\s*[?.]?\s*$", re.IGNORECASE)
_MEMORY = {"france": "Paris", "japan": "Tokyo"}  # all the flawed agent "remembers"


def _evaluate(a: str, op: str, b: str) -> float:
    x, y = float(a), float(b)
    return {"+": x + y, "-": x - y, "*": x * y, "/": x / y}[op]


def _fmt(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


class MockAgent:
    """policy='reference' uses tools correctly; policy='flawed' skips them and guesses."""

    def __init__(self, policy: str = "reference"):
        if policy not in ("reference", "flawed"):
            raise ValueError("policy must be 'reference' or 'flawed'")
        self.policy = policy

    def run(self, task: Task, registry: Registry) -> Trajectory:
        traj = Trajectory(steps=1)
        parts: list[str] = []
        arith = _ARITH.search(task.prompt)
        capital = _CAPITAL.search(task.prompt.strip())

        if arith:
            a, op, b = arith.groups()
            if self.policy == "reference" and "calculator" in registry:
                parts.append(f"The answer is {_call_tool(registry, traj, 'calculator', {'expression': f'{a} {op} {b}'})}.")
            else:  # flawed: no tool, off-by-one guess
                parts.append(f"The answer is {_fmt(_evaluate(a, op, b) + 1)}.")

        if capital:
            country = capital.group(1).strip()
            if self.policy == "reference" and "lookup" in registry:
                result = _call_tool(registry, traj, "lookup", {"key": f"capital:{country.lower()}"})
                if result == "NOT_FOUND":
                    parts.append("I could not find that in the knowledge base.")
                else:
                    parts.append(f"The capital of {country} is {result}.")
            else:  # flawed: answers from memory, hallucinates the rest
                guess = _MEMORY.get(country.lower(), f"{country}opolis")
                parts.append(f"The capital of {country} is {guess}.")

        if len(traj.tool_calls) > 1:
            traj.steps = len(traj.tool_calls) + 1
        elif traj.tool_calls:
            traj.steps = 2
        traj.final_answer = " ".join(parts) or "I don't know."
        # Rough word-count proxy so downstream metrics have something to aggregate.
        traj.input_tokens = len(task.prompt.split()) * traj.steps
        traj.output_tokens = len(traj.final_answer.split())
        return traj


class ClaudeAgent:
    """Tool-use loop against the Anthropic Messages API.

    `client` is injectable so tests can run without network access.
    """

    def __init__(self, model: str, max_steps: int = 8, max_tokens: int = 1024, system: str | None = None, client: Any = None):
        self.model = model
        self.max_steps = max_steps
        self.max_tokens = max_tokens
        self.system = system
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            try:
                import anthropic
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError("Install the optional dependency: pip install 'agent-evals-harness[claude]'") from exc
            self._client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        return self._client

    def run(self, task: Task, registry: Registry) -> Trajectory:
        client = self._get_client()
        traj = Trajectory()
        messages: list[dict[str, Any]] = [{"role": "user", "content": task.prompt}]
        tools = [t.to_anthropic() for t in registry]

        for _ in range(self.max_steps):
            kwargs: dict[str, Any] = dict(model=self.model, max_tokens=self.max_tokens, messages=messages)
            if tools:
                kwargs["tools"] = tools
            if self.system:
                kwargs["system"] = self.system
            resp = client.messages.create(**kwargs)
            traj.steps += 1
            traj.input_tokens += getattr(resp.usage, "input_tokens", 0)
            traj.output_tokens += getattr(resp.usage, "output_tokens", 0)

            if resp.stop_reason == "tool_use":
                messages.append({"role": "assistant", "content": resp.content})
                results = []
                for block in resp.content:
                    if block.type != "tool_use":
                        continue
                    out = _call_tool(registry, traj, block.name, dict(block.input))
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": out,
                            "is_error": traj.tool_calls[-1].is_error,
                        }
                    )
                messages.append({"role": "user", "content": results})
                continue

            traj.final_answer = "".join(b.text for b in resp.content if b.type == "text")
            return traj

        traj.error = f"max_steps ({self.max_steps}) reached without a final answer"
        return traj
