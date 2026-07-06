# agent/__init__.py
from agent.core import Agent
from agent import tools  # noqa: F401 — importing triggers tool registration

__all__ = ["Agent"]
