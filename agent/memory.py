"""
agent/memory.py — Conversation Memory
--------------------------------------
Manages what the agent "remembers" within a session.

Two types:
  1. Short-term (in-RAM) — conversation history, sliding window
  2. Long-term (on-disk) — persistent facts via memory_tool.py

This file handles short-term memory (the conversation thread).
"""

from dataclasses import dataclass
from typing import List, Literal
import config


@dataclass
class Message:
    """A single message in the conversation."""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    tool_name: str | None = None   # set if role == "tool"


class ConversationMemory:
    """
    Sliding-window conversation history.

    Keeps the last MEMORY_WINDOW messages so the LLM always
    has recent context without exceeding token limits.
    """

    def __init__(self, window: int = config.MEMORY_WINDOW):
        self.window = window
        self._messages: List[Message] = []

    def add(self, role: str, content: str, tool_name: str | None = None) -> None:
        """Append a new message."""
        self._messages.append(Message(role=role, content=content, tool_name=tool_name))
        # Trim to the sliding window (system prompt is passed separately, not stored here)
        if len(self._messages) > self.window:
            self._messages = self._messages[-self.window:]

    def get_history(self) -> List[Message]:
        """Return all messages in order."""
        return list(self._messages)

    def clear(self) -> None:
        """Reset the conversation."""
        self._messages = []

    def truncate_to(self, length: int) -> None:
        """
        Drop everything after the given length — used to roll back a turn
        that was cancelled mid-flight so its (possibly unanswered) user
        message doesn't linger and confuse the next turn's LLM call.
        """
        self._messages = self._messages[:length]

    def __len__(self) -> int:
        return len(self._messages)

    def summary(self) -> str:
        """Quick debug summary."""
        return f"ConversationMemory({len(self._messages)} messages, window={self.window})"
