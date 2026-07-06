"""
agent/tools/memory_tool.py — Remember & Recall Tool
-----------------------------------------------------
Lets the agent persist facts across conversations.
"Remember that my name is Darshan" → stored to disk.
"What's my name?" → recalled from disk.
"""

import json
from pathlib import Path
from agent.tools.registry import tool
import config

# Ensure data directory exists
config.MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)


def _load_facts() -> dict:
    if config.MEMORY_FILE.exists():
        return json.loads(config.MEMORY_FILE.read_text())
    return {}


def _save_facts(facts: dict) -> None:
    config.MEMORY_FILE.write_text(json.dumps(facts, indent=2))


@tool(
    name="remember",
    description=(
        "Store a fact for later recall. Use this when the user tells you "
        "something they want you to remember (name, preferences, etc.)."
    ),
    parameters={
        "key":   {"type": "string", "description": "A label for the fact, e.g. 'user_name'"},
        "value": {"type": "string", "description": "The fact to remember, e.g. 'Darshan'"},
    },
    examples=[
        {"key": "user_name",        "value": "Darshan"},
        {"key": "favorite_language","value": "Python"},
    ],
)
def remember(key: str, value: str) -> str:
    facts = _load_facts()
    facts[key] = value
    _save_facts(facts)
    return f"Remembered: {key} = {value}"


@tool(
    name="recall",
    description=(
        "Recall a previously stored fact by key. "
        "Use this when the user asks about something you might have remembered."
    ),
    parameters={
        "key": {"type": "string", "description": "The label of the fact to recall"},
    },
    examples=[
        {"key": "user_name",         "result": "Darshan"},
        {"key": "favorite_language", "result": "Python"},
    ],
)
def recall(key: str) -> str:
    facts = _load_facts()
    if key in facts:
        return f"Recalled: {key} = {facts[key]}"
    # Try fuzzy match
    matches = [k for k in facts if key.lower() in k.lower()]
    if matches:
        return f"Found similar: " + ", ".join(f"{k}={facts[k]}" for k in matches)
    return f"No memory found for key '{key}'. Known keys: {list(facts.keys())}"


@tool(
    name="list_memories",
    description="List all stored facts/memories.",
    parameters={},
)
def list_memories() -> str:
    facts = _load_facts()
    if not facts:
        return "No memories stored yet."
    return "Stored memories:\n" + "\n".join(f"  {k}: {v}" for k, v in facts.items())
