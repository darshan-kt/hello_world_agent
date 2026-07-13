"""
config.py — Central configuration for Hello Agent
--------------------------------------------------
Loads from environment variables or .env file.
This is the single source of truth for all settings.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv(Path(__file__).parent / ".env")

# ──────────────────────────────────────────────
# LLM Settings
# ──────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL      = os.getenv("LLM_MODEL", "gemini-2.5-flash")   # fast & free
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))  # lower = more deterministic
MAX_TOKENS      = int(os.getenv("MAX_TOKENS", "2048"))

# ──────────────────────────────────────────────
# Agent Settings
# ──────────────────────────────────────────────
AGENT_NAME      = os.getenv("AGENT_NAME", "Darshan-AI")
MAX_ITERATIONS  = int(os.getenv("MAX_ITERATIONS", "10"))  # ReAct loop guard

# ──────────────────────────────────────────────
# Memory Settings
# ──────────────────────────────────────────────
MEMORY_WINDOW   = int(os.getenv("MEMORY_WINDOW", "20"))   # keep last N messages
MEMORY_FILE     = Path(__file__).parent / "data" / "memory.json"

# ──────────────────────────────────────────────
# Hospital Tool Settings (POC — synthetic data only)
# ──────────────────────────────────────────────
HOSPITAL_DB_FILE = Path(__file__).parent / "data" / "hospital.db"

# ──────────────────────────────────────────────
# API Server Settings
# ──────────────────────────────────────────────
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# ──────────────────────────────────────────────
# System Prompt — The Agent's Personality & Rules
# ──────────────────────────────────────────────
SYSTEM_PROMPT = f"""
You are {AGENT_NAME}, a helpful and intelligent AI assistant.

## Your Capabilities
You have access to a set of tools (provided separately via function calling).
Call a tool only when it would meaningfully improve accuracy — arithmetic, current
weather, current events, or facts stored about this specific user. For stable,
well-known facts you're already confident about (e.g. "capital of France"), answer
directly without a tool call. You may call multiple tools, one after another,
before giving your final answer.

## Rules
1. Always be honest — if you don't know, say so.
2. Use tools when accuracy matters (math, weather, facts, current events).
3. Be concise but complete.
4. If a tool fails, explain what happened and try an alternative.
""".strip()
