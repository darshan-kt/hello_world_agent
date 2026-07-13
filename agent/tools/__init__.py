# agent/tools/__init__.py
# Import all tools here to auto-register them into the registry.
# Just add an import line to register a new tool — that's it!

from agent.tools import (
    calculator,
    weather,
    memory_tool,
    web_search,
    hospital,
)

__all__ = ["calculator", "weather", "memory_tool", "web_search", "hospital"]
