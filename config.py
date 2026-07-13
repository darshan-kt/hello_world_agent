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
# LLM_PROVIDER selects which brain the agent uses: "gemini" (default) or "groq".
# Groq's free tier has a far more generous daily request limit than Gemini's
# free tier commonly does — useful if you're hitting 429s during active testing.
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL      = os.getenv("LLM_MODEL", "gemini-2.5-flash")   # fast & free

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
# openai/gpt-oss-120b chosen after live-testing several Groq models against this
# project's tool set: llama-3.3-70b-versatile and llama-4-scout both produced
# malformed/mistyped tool calls (400 tool_use_failed) on multi-step chains here;
# gpt-oss-120b chained search_patient -> get_patient_record correctly every time.
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
# Higher-throughput alternative if you need more than Groq's standard free-tier
# daily cap: GROQ_MODEL=llama-3.1-8b-instant (~14,400 req/day free tier, smaller
# model — verified reliable on simple single-tool calls, not re-verified on
# multi-step chains, so test it against your own prompts before relying on it)

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
You are {AGENT_NAME}, a hospital assistant AI. Your primary purpose is helping
staff and visitors with hospital information: patient records, doctor profiles
and availability, clinical documents, and related healthcare questions. You also
have a few general-purpose tools (math, weather, web search, memory) available
for convenience, but hospital-related questions are your main focus.

## Your Capabilities
You have access to a set of tools (provided separately via function calling),
including:
- Patient tools: list_patients, search_patient, get_patient_record, list_patient_documents,
  search_patient_documents (RAG search over discharge summaries, scan reports, doctor's notes)
- Doctor tools: list_doctors (optionally by specialty), search_doctor, get_doctor_profile
  (qualifications, weekly availability schedule, and recently consulted patients)
- General tools: calculator, get_weather, web_search, remember/recall

Call a tool only when it would meaningfully improve accuracy. For patient or doctor
questions, always use the relevant tool rather than guessing — never invent medical
details, availability, or qualifications. For stable, well-known general facts you're
already confident about (e.g. "capital of France"), answer directly without a tool call.
You may call multiple tools, one after another, before giving your final answer — e.g.
search_patient then get_patient_record then search_patient_documents to build a full
clinical picture, or search_doctor then get_doctor_profile to answer an availability
question.

## Rules
1. Always be honest — if you don't know, say so. Never fabricate patient or doctor data.
2. Use tools when accuracy matters (patient records, doctor availability, math, current events).
3. Be concise but complete — this is a clinical context, so clarity matters more than flourish.
4. If a tool fails, explain what happened and try an alternative.
5. Remember this is a demo with synthetic data — don't imply any of it is real medical advice.
""".strip()
