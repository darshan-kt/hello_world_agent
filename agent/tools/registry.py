"""
agent/tools/registry.py — Tool Registration System
---------------------------------------------------
This is the heart of the tool system. Any Python function
decorated with @tool() becomes available to the agent.

Usage:
    from agent.tools.registry import tool, get_tool, list_tools

    @tool("calculator", description="Perform math calculations")
    def calculator(expression: str) -> str:
        return str(eval(expression))
"""

import json
import traceback
from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class ToolDefinition:
    """Metadata + callable for a registered tool."""
    name: str
    description: str
    parameters: Dict[str, Any]   # JSON Schema for inputs
    func: Callable
    examples: list = field(default_factory=list)


# Global tool registry (singleton pattern)
_REGISTRY: Dict[str, ToolDefinition] = {}


def tool(
    name: str,
    description: str,
    parameters: Optional[Dict[str, Any]] = None,
    examples: Optional[list] = None,
):
    """
    Decorator to register a function as an agent tool.

    Args:
        name: Unique tool identifier (used by the agent in Action: lines)
        description: What the tool does — the LLM reads this!
        parameters: JSON Schema dict describing expected inputs
        examples: Optional list of example inputs/outputs

    Example:
        @tool(
            "calculator",
            description="Evaluate a math expression and return the result",
            parameters={"expression": {"type": "string", "description": "Math expression"}},
        )
        def my_calc(expression: str) -> str:
            return str(eval(expression))
    """
    def decorator(func: Callable) -> Callable:
        _REGISTRY[name] = ToolDefinition(
            name=name,
            description=description,
            parameters=parameters or {},
            func=func,
            examples=examples or [],
        )
        return func
    return decorator


def get_tool(name: str) -> Optional[ToolDefinition]:
    """Retrieve a tool by name."""
    return _REGISTRY.get(name)


def list_tools() -> Dict[str, ToolDefinition]:
    """Return all registered tools."""
    return dict(_REGISTRY)


def run_tool(name: str, input_data: Dict[str, Any]) -> str:
    """
    Execute a tool by name with given inputs.

    Returns a string observation (success or error message).
    The agent feeds this back into its context as an Observation.
    """
    tool_def = get_tool(name)
    if not tool_def:
        return f"ERROR: Tool '{name}' not found. Available tools: {list(_REGISTRY.keys())}"

    try:
        result = tool_def.func(**input_data)
        return str(result)
    except Exception as e:
        return f"ERROR running tool '{name}': {e}\n{traceback.format_exc()}"


def tools_prompt() -> str:
    """
    Generate the tool list string injected into the system prompt.
    The LLM reads this to know what tools exist and how to call them.
    """
    if not _REGISTRY:
        return "No tools available."

    lines = ["## Available Tools\n"]
    for name, t in _REGISTRY.items():
        lines.append(f"### {name}")
        lines.append(f"Description: {t.description}")
        if t.parameters:
            lines.append(f"Parameters: {json.dumps(t.parameters, indent=2)}")
        if t.examples:
            lines.append(f"Examples: {json.dumps(t.examples, indent=2)}")
        lines.append("")
    return "\n".join(lines)
