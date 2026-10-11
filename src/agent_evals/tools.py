"""A tiny tool registry plus two built-in tools used by the example suite."""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass
from typing import Any, Callable

_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
_UNARY_OPS = {ast.USub: operator.neg, ast.UAdd: operator.pos}


def safe_eval(expression: str) -> float | int:
    """Evaluate basic arithmetic only. No names, calls, or exponentiation."""

    def _eval(node: ast.AST) -> float | int:
        if isinstance(node, ast.Expression):
            return _eval(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN_OPS:
            return _BIN_OPS[type(node.op)](_eval(node.left), _eval(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPS:
            return _UNARY_OPS[type(node.op)](_eval(node.operand))
        raise ValueError(f"unsupported expression: {expression!r}")

    return _eval(ast.parse(expression.strip(), mode="eval"))


def _fmt_number(value: float | int) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


def calculator(expression: str) -> str:
    return _fmt_number(safe_eval(expression))


_KB = {
    "capital:france": "Paris",
    "capital:japan": "Tokyo",
    "capital:canada": "Ottawa",
    "capital:australia": "Canberra",
}


def lookup(key: str) -> str:
    return _KB.get(key.strip().lower(), "NOT_FOUND")


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    fn: Callable[..., str]

    def to_anthropic(self) -> dict[str, Any]:
        """Tool definition in the shape the Anthropic Messages API expects."""
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema}


BUILTIN_TOOLS: dict[str, Tool] = {
    "calculator": Tool(
        name="calculator",
        description="Evaluate a basic arithmetic expression such as '17 + 25'. Supports + - * / // %.",
        input_schema={
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "Arithmetic expression"}},
            "required": ["expression"],
        },
        fn=calculator,
    ),
    "lookup": Tool(
        name="lookup",
        description="Look up a fact in a small knowledge base. Keys look like 'capital:france'. Returns NOT_FOUND if unknown.",
        input_schema={
            "type": "object",
            "properties": {"key": {"type": "string", "description": "Knowledge base key"}},
            "required": ["key"],
        },
        fn=lookup,
    ),
}


class Registry:
    def __init__(self, tools: list[Tool]):
        self._tools = {t.name: t for t in tools}

    def __iter__(self):
        return iter(self._tools.values())

    def __contains__(self, name: str) -> bool:
        return name in self._tools

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)


def build_registry(names: list[str]) -> Registry:
    unknown = [n for n in names if n not in BUILTIN_TOOLS]
    if unknown:
        raise ValueError(f"unknown tool(s): {unknown}. Available: {sorted(BUILTIN_TOOLS)}")
    return Registry([BUILTIN_TOOLS[n] for n in names])
