"""Exact arithmetic for the `calculate` tool.

Small local models get multiplication wrong while sounding sure ("17 × 23 =
289"), so numbers come from here, not from the model. Only arithmetic is
evaluated: the expression is parsed to an AST and walked; names, calls and
attributes are rejected, so nothing in it can run code.
"""
from __future__ import annotations

import ast
import math
import operator
import re

_BINARY = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_FUNCTIONS = {"sqrt": math.sqrt, "abs": abs, "round": round}
_MAX_EXPONENT = 1000


class CalculationError(ValueError):
    pass


def _normalize(expression: str) -> str:
    text = (expression or "").strip().lower()
    text = text.replace("×", "*").replace("÷", "/").replace("^", "**").replace(",", "")
    text = re.sub(r"(\d+(?:\.\d+)?)\s*%\s*of\s*", r"(\1/100)*", text)   # "15% of 80"
    text = re.sub(r"(\d)\s*x\s*(\d)", r"\1*\2", text)                    # "17 x 23"
    return text


def _eval(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise CalculationError("exponent too large")
        return _BINARY[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FUNCTIONS
            and not node.keywords):
        return _FUNCTIONS[node.func.id](*(_eval(a) for a in node.args))
    raise CalculationError("only numbers, + - * / // % ** and sqrt/abs/round are allowed")


def calculate(expression: str) -> str:
    """Evaluate an arithmetic expression; returns 'expr = result' or an error line."""
    text = _normalize(expression)
    if not text or len(text) > 200:
        return "Error: give a short arithmetic expression, e.g. 17*23"
    try:
        value = _eval(ast.parse(text, mode="eval"))
    except ZeroDivisionError:
        return "Error: division by zero"
    except (CalculationError, SyntaxError, TypeError, ValueError, OverflowError) as e:
        return f"Error: can't calculate {expression!r}: {e}"
    if isinstance(value, float) and value.is_integer() and abs(value) < 1e15:
        value = int(value)
    elif isinstance(value, float):
        value = round(value, 10)
    return f"{expression.strip()} = {value}"
