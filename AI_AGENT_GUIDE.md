# Demystifying AI Agents: The "Hello Agent" Guide 🤖

Welcome to the world of AI Agents! If you've ever used ChatGPT, you know that AI can answer questions. But an **AI Agent** takes this a step further: it doesn't just talk—it **thinks, plans, and takes action**.

This document will break down what an AI Agent is, how it works, and how the `hello_agent` project (which runs as an agent named **Darshan-AI**) implements these concepts. We have written this specifically for non-engineers looking to build a career in AI.

---

## 1. What is an AI Agent?

Imagine you ask a normal chatbot: *"What is the weather in Copenhagen today?"*
A normal chatbot might say: *"I don't know, my training data ended in 2023."*

If you ask an **AI Agent** the same question, it acts like a human assistant:
1. **Thought:** "I need to check the current weather for Copenhagen. I will use a weather tool."
2. **Action:** *Calls the weather tool for Copenhagen.*
3. **Observation:** *Sees that it is 18°C and rainy.*
4. **Final Answer:** *"It's currently 18°C and rainy in Copenhagen!"*

And this is exactly what this project does — the weather answer comes from a **real live API**, not a canned response.

> [!NOTE]
> **The Core Difference:**
> A standard AI model generates text based on patterns. An AI **Agent** is given **Tools** (like a calculator, web search, or database access) and the autonomy to use them to solve problems.

---

## 2. The Anatomy of an AI Agent

Every effective AI agent requires three main components. Think of it like building a digital employee.

### 🧠 1. The Brain (The LLM)
The agent needs a Large Language Model to process language, understand the user's intent, and make logical decisions. This project uses **Google Gemini 2.5 Flash** (free tier) — but the architecture works with any LLM.

### 🧰 2. The Hands (Tools)
Tools are how the agent interacts with the real world. `hello_agent` is a **hospital assistant**, so most
of its tools are healthcare-focused, plus a few general-purpose ones for convenience:

| Tool | What it does | Powered by |
| :--- | :--- | :--- |
| **search_patient / get_patient_record** | Find a patient and pull their full medical record | SQLite (synthetic patient DB) |
| **search_patient_documents** | Search a patient's discharge summaries, scans, and notes | Keyword-overlap RAG over real text |
| **list_doctors / search_doctor / get_doctor_profile** | Find a specialist and see their qualifications, weekly schedule, and recent patients | SQLite (synthetic doctor DB) |
| **calculator** | Accurate math (LLMs are bad at arithmetic!) | Safe Python evaluation |
| **web_search** | Look up real-time information on the internet | DuckDuckGo (free, no API key) |
| **get_weather** | Live weather for any city worldwide | Open-Meteo (free, no API key) |
| **remember / recall** | Store and retrieve facts about the user | JSON file on disk |

See [HOSPITAL_RAG_ARCHITECTURE.md](HOSPITAL_RAG_ARCHITECTURE.md) for the full patient + doctor data model.

### 💾 3. The Notebook (Memory)
To hold a conversation, the agent needs to remember what was said five minutes ago.
- **Short-term memory**: a sliding window of the current chat session (`agent/memory.py`).
- **Long-term memory**: facts stored on disk that survive restarts (`data/memory.json` via the remember/recall tools).

---

## 3. How it Works: The ReAct Loop

The secret sauce of modern AI agents is the **ReAct (Reasoning + Acting) Loop**. It forces the AI to stop and think out loud before doing anything.

Here is a visual representation of how the agent thinks:

```mermaid
graph TD
    User(["User asks: Who is the Prime Minister of India?"]) --> T1

    subgraph The ReAct Loop
    T1["🧠 THOUGHT: I don't know this off the top of my head. I need to search the web."] --> A1
    A1["⚡ ACTION: Call 'web_search' Tool"] --> O1
    O1["👁️ OBSERVATION: Search results return 'Narendra Modi'"] --> T2
    T2["🧠 THOUGHT: I have the answer now."] --> F1
    end

    F1(["Final Answer: The Prime Minister of India is Narendra Modi."])

    classDef loop fill:#1f2937,stroke:#3b82f6,stroke-width:2px,color:#fff;
    class T1,A1,O1,T2 loop;
```

As long as the agent needs more information, it will continue cycling through Thought → Action → Observation. It can even chain multiple tools for one question — ask it *"What is 256 × 17, and what's the weather in Bengaluru?"* and it will use the calculator **and** the weather tool before answering.

In the web UI, all of this happens behind a simple spinner — you just see "Thinking… → Using web_search…" and then a clean final answer.

---

## 4. Mapping Concepts to the `hello_agent` Codebase

Now that you understand the concepts, let's look at how the code actually works. If you ever want to expand this project, you now know exactly where to look!

| Concept | File in Project | What it does |
| :--- | :--- | :--- |
| **The Loop** | `agent/core.py` | This is the engine room. It contains the exact code that forces the AI to output "Thought:", "Action:", and "Final Answer:". |
| **Memory** | `agent/memory.py` | This keeps track of the chat history so the AI doesn't get amnesia after every message. |
| **The Tools** | `agent/tools/` | This folder holds the agent's capabilities. Want the agent to send emails? You would create `agent/tools/email.py` and register it with one `@tool()` decorator! |
| **The Body** | `api/server.py` & `web/` | This provides the user interface (browser chat with live streaming) so humans can interact with the agent easily. |
| **The Settings** | `config.py` & `.env` | The agent's name (Darshan-AI), which model it uses, how many tool-loops it may run, and its personality (system prompt). |

---

## 5. Try It Yourself

The whole system runs with one command (you just need Docker and a free Gemini API key in `.env`):

```bash
docker compose up -d        # → open http://localhost:8000
```

Things to try in the chat:
- *"Which cardiologists are available today?"* → filters doctors by specialty + schedule
- *"Summarize patient 1's medical history, including any scan findings"* → chains patient + document tools
- *"Tell me about Dr. Krishnan's qualifications"* → doctor profile lookup
- *"What is 15% of 340?"* → watch it use the calculator
- *"Remember that my favorite color is blue"* → then ask about it tomorrow!

Or skip the chat entirely — click **Patients** or **Doctors** in the sidebar to browse the synthetic
hospital records directly (instant, no AI call), then click any card for a full chart/profile and an
optional **✨ Generate AI Summary** button.

> [!TIP]
> **Career Advice for AI Builders:**
> You don't need to invent new AI models to be valuable in the AI industry. The future belongs to people who know how to take existing models (like Gemini) and wire them up with tools, memory, and ReAct loops to solve real-world business problems.

---

## 6. Summary

Building an AI agent is simply taking a smart chatbot and giving it a strict framework (the **ReAct loop**) and a set of instructions (**Tools**) to interact with the outside world. By exploring and modifying the `hello_agent` project, you now possess the foundational blueprint used by top tech companies to build autonomous AI systems.
