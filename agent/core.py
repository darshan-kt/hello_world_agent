"""
agent/core.py — The Agent Brain (ReAct Loop)
---------------------------------------------
This is THE most important file. It implements the ReAct pattern:

  1. THINK  — LLM reasons about what to do
  2. ACT    — LLM calls a tool (or gives final answer)
  3. OBSERVE — Tool result is fed back to LLM
  4. REPEAT — Until final answer or max iterations

This loop is the same pattern used in:
  - OpenAI Assistants API
  - LangChain AgentExecutor
  - Amazon Bedrock Agents
  - Google Vertex AI Agents

Understanding this file = understanding how ALL agents work.

Two LLM providers are supported (config.LLM_PROVIDER):
  - "gemini" (default) — Google's native function-calling API
  - "groq"              — OpenAI-compatible chat-completions + tools API,
                           useful when Gemini's free-tier daily quota is hit

Both use real structured function calling (not text-parsed "Action:" lines)
— tool schemas travel as API metadata and arguments arrive pre-parsed and
schema-checked, regardless of which provider is active. The two providers'
SDKs return meaningfully different response shapes, so each gets its own
`_run_*` generator; `run()` just dispatches to the active one.
"""

import json
import logging
import threading
from typing import Generator, Optional

import config
from agent.memory import ConversationMemory
from agent.tools.registry import run_tool, to_function_declarations, to_openai_tools

logger = logging.getLogger(__name__)


class AgentStep:
    """Represents one step in the ReAct loop — for streaming to the UI."""
    def __init__(self, step_type: str, content: str, tool_name: str = ""):
        self.type = step_type      # "thought" | "action" | "observation" | "answer" | "error" | "cancelled"
        self.content = content
        self.tool_name = tool_name

    def to_dict(self) -> dict:
        return {"type": self.type, "content": self.content, "tool_name": self.tool_name}


class Agent:
    """
    The core AI agent.

    Responsibilities:
      - Maintains conversation memory
      - Builds the provider-specific request (Gemini contents / Groq messages)
      - Runs the ReAct loop via native function calling
      - Dispatches tool calls
      - Returns the final answer
    """

    def __init__(self):
        self.provider = config.LLM_PROVIDER if config.LLM_PROVIDER in ("gemini", "groq") else "gemini"
        self.memory = ConversationMemory()
        self.name = config.AGENT_NAME

        if self.provider == "groq":
            self._init_groq()
        else:
            self._init_gemini()

        logger.info(f"Agent '{self.name}' initialized with provider '{self.provider}', model '{self.model_name}'")

    def _init_gemini(self) -> None:
        if not config.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY not set. Copy .env.example to .env and add your key.\n"
                "Get a free key at: https://aistudio.google.com/apikey"
            )
        from google import genai
        from google.genai import types as genai_types

        self._genai_types = genai_types
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model_name = config.LLM_MODEL
        self.gen_config = genai_types.GenerateContentConfig(
            temperature=config.LLM_TEMPERATURE,
            max_output_tokens=config.MAX_TOKENS,
            system_instruction=config.SYSTEM_PROMPT,
            tools=[genai_types.Tool(function_declarations=to_function_declarations())],
        )

    def _init_groq(self) -> None:
        if not config.GROQ_API_KEY:
            raise ValueError(
                "GROQ_API_KEY not set (LLM_PROVIDER=groq). Add it to .env.\n"
                "Get a free key at: https://console.groq.com/keys"
            )
        from groq import Groq

        self.client = Groq(api_key=config.GROQ_API_KEY)
        self.model_name = config.GROQ_MODEL
        self.openai_tools = to_openai_tools()

    def _demo_fallback(self, user_message: str) -> dict:
        """
        Dynamic mock "brain" used when the active provider's API key is invalid
        — e.g. in sandbox environments — so the ReAct loop is still demonstrable.

        Returns a dict shaped like a real turn's outcome: either an
        {"action": name, "args": {...}} to call a tool, or a
        {"final_answer": text} to stop.
        """
        msg = (user_message or "").lower()
        history = self.memory.get_history()
        last_msg = history[-1] if history else None

        if last_msg and last_msg.role == "tool":
            return {"final_answer": f"Based on the data: {last_msg.content}"}
        if "weather" in msg:
            city = msg.split("weather in ")[-1].strip().rstrip("?.!,") if "weather in " in msg else "unknown"
            return {"action": "get_weather", "args": {"city": city}}
        if "calculate" in msg or "math" in msg or "+" in msg or "*" in msg:
            return {"action": "calculator", "args": {"expression": "42"}}
        clean_query = user_message.replace('"', '') if user_message else ""
        return {"action": "web_search", "args": {"query": clean_query}}

    def run(
        self, user_message: str, cancel_event: Optional[threading.Event] = None
    ) -> Generator[AgentStep, None, None]:
        """
        Run the ReAct loop for a user message.

        This is a generator — it yields AgentStep objects as they happen,
        allowing the UI to stream thoughts, actions, and observations in real time.

        `cancel_event`, if given, is polled between LLM round-trips and between
        individual tool calls (the loop's natural checkpoints). Setting it stops
        the loop at the next checkpoint and yields a "cancelled" step — it can't
        interrupt an LLM call that's already in flight, since neither provider's
        SDK is called in a way that supports aborting a request mid-flight here.

        Usage:
            for step in agent.run("What's 2 + 2?"):
                print(step.type, step.content)
        """
        if self.provider == "groq":
            yield from self._run_groq(user_message, cancel_event)
        else:
            yield from self._run_gemini(user_message, cancel_event)

    # ──────────────────────────────────────────────
    # Gemini (native function calling)
    # ──────────────────────────────────────────────

    def _build_gemini_contents(self) -> list:
        """
        Convert conversation memory into Gemini `Content` turns.

        Past tool observations are flattened to plain text here — they're
        just historical context by the time a new run() starts, not part
        of an in-flight function-call/function-response exchange (those
        are only needed within a single run(), see the loop below).
        """
        types_ = self._genai_types
        contents = []
        for msg in self.memory.get_history():
            if msg.role == "user":
                contents.append(types_.Content(role="user", parts=[types_.Part(text=msg.content)]))
            elif msg.role in ("assistant", "tool"):
                contents.append(types_.Content(role="model", parts=[types_.Part(text=msg.content)]))
        return contents

    def _run_gemini(
        self, user_message: str, cancel_event: Optional[threading.Event] = None
    ) -> Generator[AgentStep, None, None]:
        types_ = self._genai_types
        self.memory.add("user", user_message)
        contents = self._build_gemini_contents()
        demo_mode = False

        for iteration in range(config.MAX_ITERATIONS):
            if cancel_event and cancel_event.is_set():
                yield AgentStep("cancelled", "Request cancelled.")
                return

            if demo_mode:
                outcome = self._demo_fallback(user_message if iteration == 0 else "")
            else:
                try:
                    response = self.client.models.generate_content(
                        model=self.model_name,
                        contents=contents,
                        config=self.gen_config,
                    )
                except Exception as e:
                    if "API key not valid" in str(e) or "API_KEY_INVALID" in str(e):
                        demo_mode = True
                        outcome = self._demo_fallback(user_message if iteration == 0 else "")
                    else:
                        yield AgentStep("error", f"LLM error: {e}")
                        return

                if not demo_mode:
                    if not response.candidates or not response.candidates[0].content.parts:
                        yield AgentStep(
                            "error",
                            "LLM returned an empty response (possibly blocked by safety filters). "
                            "Try rephrasing your message.",
                        )
                        return

                    model_content = response.candidates[0].content
                    contents.append(model_content)

                    function_calls = [p.function_call for p in model_content.parts if p.function_call]
                    thoughts = [p.text for p in model_content.parts if p.text and p.thought]
                    answer_text = "".join(
                        p.text for p in model_content.parts if p.text and not p.thought
                    ).strip()

                    for t in thoughts:
                        yield AgentStep("thought", t.strip())

                    if function_calls:
                        outcome = {"calls": function_calls}
                    elif answer_text:
                        outcome = {"final_answer": answer_text}
                    else:
                        yield AgentStep(
                            "error",
                            "LLM returned an empty response (possibly blocked by safety filters). "
                            "Try rephrasing your message.",
                        )
                        return

            if "final_answer" in outcome:
                self.memory.add("assistant", outcome["final_answer"])
                yield AgentStep("answer", outcome["final_answer"])
                return

            if "action" in outcome:  # demo mode: single synthetic call
                calls = [(outcome["action"], outcome["args"])]
            else:  # real mode: one or more native function calls
                calls = [(fc.name, dict(fc.args)) for fc in outcome["calls"]]

            response_parts = []
            for tool_name, tool_input in calls:
                if cancel_event and cancel_event.is_set():
                    yield AgentStep("cancelled", "Request cancelled.")
                    return

                yield AgentStep("action", json.dumps(tool_input), tool_name=tool_name)

                observation = run_tool(tool_name, tool_input)
                yield AgentStep("observation", observation, tool_name=tool_name)

                obs_text = f"Observation from {tool_name}: {observation}"
                self.memory.add("tool", obs_text, tool_name=tool_name)

                if not demo_mode:
                    response_parts.append(
                        types_.Part.from_function_response(
                            name=tool_name, response={"result": observation}
                        )
                    )

            if demo_mode:
                # No real function-call turn to answer — the next iteration's
                # _demo_fallback() reads the tool observation straight from memory.
                continue

            contents.append(types_.Content(role="user", parts=response_parts))

        yield AgentStep(
            "error",
            f"Reached maximum iterations ({config.MAX_ITERATIONS}). "
            "The task may be too complex. Try breaking it into smaller steps."
        )

    # ──────────────────────────────────────────────
    # Groq (OpenAI-compatible chat completions + tools)
    # ──────────────────────────────────────────────

    def _build_groq_messages(self) -> list:
        """
        Convert conversation memory into OpenAI-style chat messages.

        Same flattening rule as the Gemini side: past tool observations become
        plain assistant-role text, since the strict tool_call_id pairing the
        API enforces is only meaningful within a single in-flight run().
        """
        messages = [{"role": "system", "content": config.SYSTEM_PROMPT}]
        for msg in self.memory.get_history():
            if msg.role == "user":
                messages.append({"role": "user", "content": msg.content})
            elif msg.role in ("assistant", "tool"):
                messages.append({"role": "assistant", "content": msg.content})
        return messages

    def _run_groq(
        self, user_message: str, cancel_event: Optional[threading.Event] = None
    ) -> Generator[AgentStep, None, None]:
        import groq

        self.memory.add("user", user_message)
        messages = self._build_groq_messages()
        demo_mode = False

        for iteration in range(config.MAX_ITERATIONS):
            if cancel_event and cancel_event.is_set():
                yield AgentStep("cancelled", "Request cancelled.")
                return

            if demo_mode:
                outcome = self._demo_fallback(user_message if iteration == 0 else "")
            else:
                try:
                    response = self.client.chat.completions.create(
                        model=self.model_name,
                        messages=messages,
                        tools=self.openai_tools,
                        tool_choice="auto",
                        temperature=config.LLM_TEMPERATURE,
                        max_completion_tokens=config.MAX_TOKENS,
                    )
                except groq.AuthenticationError:
                    demo_mode = True
                    outcome = self._demo_fallback(user_message if iteration == 0 else "")
                except Exception as e:
                    yield AgentStep("error", f"LLM error: {e}")
                    return

                if not demo_mode:
                    choice = response.choices[0]
                    reply = choice.message

                    # Replay only the fields the API actually needs — reply also carries
                    # Groq-specific extras (reasoning, executed_tools, ...) that shouldn't
                    # round-trip into the next request.
                    if reply.tool_calls:
                        messages.append({
                            "role": "assistant",
                            "content": reply.content,
                            "tool_calls": [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                                }
                                for tc in reply.tool_calls
                            ],
                        })
                        outcome = {"calls": reply.tool_calls}
                    elif (reply.content or "").strip():
                        messages.append({"role": "assistant", "content": reply.content})
                        outcome = {"final_answer": reply.content.strip()}
                    else:
                        yield AgentStep(
                            "error",
                            "LLM returned an empty response (possibly blocked by safety filters). "
                            "Try rephrasing your message.",
                        )
                        return

            if "final_answer" in outcome:
                self.memory.add("assistant", outcome["final_answer"])
                yield AgentStep("answer", outcome["final_answer"])
                return

            if "action" in outcome:  # demo mode: single synthetic call, no tool_call_id needed
                calls = [(None, outcome["action"], outcome["args"])]
            else:  # real mode: one or more native tool calls
                calls = []
                for tc in outcome["calls"]:
                    try:
                        tool_input = json.loads(tc.function.arguments or "{}")
                    except json.JSONDecodeError:
                        tool_input = {}
                    calls.append((tc.id, tc.function.name, tool_input))

            for tool_call_id, tool_name, tool_input in calls:
                if cancel_event and cancel_event.is_set():
                    yield AgentStep("cancelled", "Request cancelled.")
                    return

                yield AgentStep("action", json.dumps(tool_input), tool_name=tool_name)

                observation = run_tool(tool_name, tool_input)
                yield AgentStep("observation", observation, tool_name=tool_name)

                obs_text = f"Observation from {tool_name}: {observation}"
                self.memory.add("tool", obs_text, tool_name=tool_name)

                if not demo_mode:
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call_id,
                        "content": observation,
                    })

            if demo_mode:
                continue

        yield AgentStep(
            "error",
            f"Reached maximum iterations ({config.MAX_ITERATIONS}). "
            "The task may be too complex. Try breaking it into smaller steps."
        )

    def chat(self, user_message: str) -> str:
        """
        Simpler synchronous interface — just returns the final answer string.
        Useful for CLI and testing.
        """
        final = ""
        for step in self.run(user_message):
            if step.type == "answer":
                final = step.content
        return final

    def reset(self) -> None:
        """Clear conversation history (start a new session)."""
        self.memory.clear()
        logger.info("Agent memory cleared.")
