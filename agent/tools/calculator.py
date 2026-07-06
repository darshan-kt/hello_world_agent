"""
agent/tools/calculator.py — Math Tool
--------------------------------------
Gives the agent ability to do accurate math.
(LLMs are notoriously bad at arithmetic — always use a tool!)
"""

import math
import operator
from agent.tools.registry import tool


@tool(
    name="calculator",
    description=(
        "Evaluate a mathematical expression. Use this for ANY arithmetic, "
        "algebra, or numeric computation. Never guess math — always use this tool."
    ),
    parameters={
        "expression": {
            "type": "string",
            "description": "A valid Python math expression, e.g. '2 ** 10' or 'math.sqrt(144)'",
        }
    },
    examples=[
        {"expression": "2 + 2",            "result": "4"},
        {"expression": "math.sqrt(144)",   "result": "12.0"},
        {"expression": "15 * 24 / 3",      "result": "120.0"},
    ],
)
def calculator(expression: str) -> str:
    """Safely evaluate a math expression."""
    # Safe eval: only allow math operations and math module
    allowed_globals = {
        "__builtins__": {},
        "math": math,
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "sum": sum,
        "pow": pow,
    }
    try:
        result = eval(expression, allowed_globals)  # noqa: S307
        return f"Result: {result}"
    except ZeroDivisionError:
        return "Error: Division by zero"
    except Exception as e:
        return f"Error evaluating '{expression}': {e}"
