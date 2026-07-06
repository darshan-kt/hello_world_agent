# Hello Agent 🤖
### The "Hello World" of AI Agents — Production-Quality Reference Project

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)](https://fastapi.tiangolo.com)
[![Gemini](https://img.shields.io/badge/LLM-Gemini%202.0%20Flash-purple.svg)](https://aistudio.google.com)

> Built the same way AI agents are built at **Google**, **Amazon**, and **OpenAI**.
> Use this as a reference or starting point for any agent project.

---

## 🧠 What Is an AI Agent?

An AI agent is a program that:
1. **Perceives** — receives input (user messages, sensor data, etc.)
2. **Reasons** — uses an LLM to plan what to do
3. **Acts** — calls tools (APIs, databases, code runners)
4. **Observes** — sees the result and updates its understanding
5. **Repeats** — loops until it has a final answer

This project implements the **ReAct pattern** (Reasoning + Acting), which is the foundation of:
- OpenAI's Assistants API
- LangChain's AgentExecutor
- Amazon Bedrock Agents
- Google Vertex AI Agents

---

## ✨ Features

| Feature | Details |
|---|---|
| 🔄 **ReAct Loop** | Full think → act → observe → repeat cycle |
| 🔧 **Tool System** | Add any function as a tool with `@tool()` decorator |
| 💾 **Memory** | Short-term (conversation) + long-term (JSON persistence) |
| 🌐 **Web UI** | Beautiful dark chat interface with real-time streaming |
| 🖥️ **CLI** | Rich terminal interface for testing |
| ⚡ **WebSocket** | Real-time step-by-step visualization |
| 🔌 **FastAPI** | REST + WebSocket backend |
| 📦 **Zero Lock-in** | Pure Python, no LangChain/AutoGen required |

---

## 🚀 Quick Start

### 1. Clone and set up
```bash
git clone <your-repo-url>
cd hello_agent

# Create virtual environment
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# Install dependencies
pip install -r requirements.txt
```

### 2. Get your FREE API key
```
https://aistudio.google.com/apikey
```
It's free. Takes 30 seconds.

### 3. Configure
```bash
cp .env.example .env
# Edit .env and paste your GEMINI_API_KEY
```

### 4. Run

**CLI mode (great for testing):**
```bash
python main.py
```

**Web UI mode:**
```bash
python main.py --server
# Open http://localhost:8000
```

**Single message:**
```bash
python main.py --message "What is sqrt(256) * 3?"
```

---

## 📁 Project Structure

```
hello_agent/
│
├── agent/                    ← CORE AGENT LOGIC
│   ├── core.py               ← ★ THE REACT LOOP (start here!)
│   ├── memory.py             ← Conversation history
│   └── tools/
│       ├── registry.py       ← @tool() decorator system
│       ├── calculator.py     ← Math tool
│       ├── weather.py        ← Weather tool (mock → real API)
│       ├── web_search.py     ← Search tool (mock → Tavily/SerpAPI)
│       └── memory_tool.py    ← Remember/recall facts
│
├── api/
│   └── server.py             ← FastAPI REST + WebSocket server
│
├── web/
│   ├── index.html            ← Chat UI
│   ├── style.css             ← Dark glassmorphism design
│   └── app.js                ← WebSocket + real-time rendering
│
├── data/                     ← Auto-created, stores long-term memory
│   └── memory.json
│
├── config.py                 ← All settings (reads from .env)
├── main.py                   ← CLI entry point
├── requirements.txt
├── .env.example
└── README.md                 ← You are here
```

---

## 🔄 The ReAct Loop (Core Concept)

```
User: "What is 2^10?"

Agent thinks:
  Thought: The user wants 2 to the power of 10. I should use the calculator.
  Action: calculator
  Action Input: {"expression": "2 ** 10"}

Tool runs:
  Observation: Result: 1024

Agent thinks:
  Thought: I have the answer.
  Final Answer: 2^10 = 1024
```

This loop is in `agent/core.py`. Read it — it's ~100 lines and teaches you everything.

---

## 🔧 Adding Your Own Tool

It takes **5 lines**:

```python
# In any file inside agent/tools/
from agent.tools.registry import tool

@tool(
    name="my_tool",
    description="What this tool does — the LLM reads this!",
    parameters={"input": {"type": "string", "description": "The input"}},
)
def my_tool(input: str) -> str:
    return f"Processed: {input}"
```

Then add one import in `agent/tools/__init__.py`:
```python
from agent.tools import my_tool_file
```

That's it. The agent will automatically know about and use your tool.

---

## 🔌 Connecting Real APIs

The tools are mocked for demo purposes. Replace them with real APIs:

### Real Web Search (Tavily — Free Tier)
```bash
pip install tavily-python
```
```python
# In agent/tools/web_search.py
from tavily import TavilyClient
client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

def web_search(query: str) -> str:
    results = client.search(query)
    return results["answer"]
```

### Real Weather (OpenWeatherMap — Free Tier)
```bash
# In agent/tools/weather.py
import httpx
resp = httpx.get(f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={KEY}")
```

### Different LLM
```python
# In config.py — switch to any model:
LLM_MODEL = "gemini-1.5-pro"     # More powerful
LLM_MODEL = "gemini-2.0-flash"   # Faster/cheaper (default)
```

---

## 🏗️ Scaling Up

This reference shows the fundamentals. Production agents add:

| Feature | How to Add |
|---|---|
| **RAG** | Add a `vector_search` tool with ChromaDB/Pinecone |
| **Multi-Agent** | Have the agent spin up sub-agents as tools |
| **Streaming LLM** | Use `generate_content_stream()` in Gemini |
| **Auth** | Add FastAPI middleware |
| **Database** | Replace `memory.json` with PostgreSQL |
| **Deployment** | Dockerize + deploy to Cloud Run / ECS |

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/

# Test a specific tool
python -c "from agent.tools.calculator import calculator; print(calculator('2**10'))"

# Test the full agent loop
python main.py --message "What is 15% of 340?"
```

---

## 📖 Key Files to Read (in Order)

1. `config.py` — Settings and system prompt
2. `agent/tools/registry.py` — How tools work
3. `agent/memory.py` — How memory works
4. `agent/core.py` — **The ReAct loop** ← most important
5. `api/server.py` — How the web server wraps the agent
6. `agent/tools/calculator.py` — Simple tool example

---

## 📜 License

MIT — use freely for any project.

---

*Built as a reference by an AI agent engineer. Push to GitHub and use as your starting point!*
