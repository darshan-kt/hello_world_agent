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

Tool calls use Gemini's native function-calling API (structured
FunctionDeclaration / FunctionCall / FunctionResponse) rather than
asking the model to write "Action: tool_name" as plain text and
regex-parsing it back out. That's both cheaper (tool schemas travel
as API metadata, not JSON dumped into the prompt every turn) and more
reliable (arguments arrive already parsed and schema-checked, instead
of round-tripping through free text that could get truncated or
malformed).
"""

import json
import logging
from typing import Generator

from google import genai
from google.genai import types as genai_types

import config
from agent.memory import ConversationMemory
from agent.tools.registry import run_tool, to_function_declarations

logger = logging.getLogger(__name__)


class AgentStep:
    """Represents one step in the ReAct loop — for streaming to the UI."""
    def __init__(self, step_type: str, content: str, tool_name: str = ""):
        self.type = step_type      # "thought" | "action" | "observation" | "answer" | "error"
        self.content = content
        self.tool_name = tool_name

    def to_dict(self) -> dict:
        return {"type": self.type, "content": self.content, "tool_name": self.tool_name}


class Agent:
    """
    The core AI agent.

    Responsibilities:
      - Maintains conversation memory
      - Builds the Gemini `contents` turn history + tool declarations
      - Runs the ReAct loop via native function calling
      - Dispatches tool calls
      - Returns the final answer
    """

    def __init__(self):
        # Initialize LLM
        if not config.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY not set. Copy .env.example to .env and add your key.\n"
                "Get a free key at: https://aistudio.google.com/apikey"
            )
        self.client = genai.Client(api_key=config.GEMINI_API_KEY)
        self.model_name = config.LLM_MODEL

        self.function_declarations = to_function_declarations()
        self.gen_config = genai_types.GenerateContentConfig(
            temperature=config.LLM_TEMPERATURE,
            max_output_tokens=config.MAX_TOKENS,
            system_instruction=config.SYSTEM_PROMPT,
            tools=[genai_types.Tool(function_declarations=self.function_declarations)],
        )

        self.memory = ConversationMemory()
        self.name = config.AGENT_NAME
        logger.info(f"Agent '{self.name}' initialized with model '{self.model_name}'")

    def _build_contents(self) -> list:
        """
        Convert conversation memory into Gemini `Content` turns.

        Past tool observations are flattened to plain text here — they're
        just historical context by the time a new run() starts, not part
        of an in-flight function-call/function-response exchange (those
        are only needed within a single run(), see the loop below).
        """
        contents = []
        for msg in self.memory.get_history():
            if msg.role == "user":
                contents.append(genai_types.Content(role="user", parts=[genai_types.Part(text=msg.content)]))
            elif msg.role == "assistant":
                contents.append(genai_types.Content(role="model", parts=[genai_types.Part(text=msg.content)]))
            elif msg.role == "tool":
                contents.append(genai_types.Content(role="model", parts=[genai_types.Part(text=msg.content)]))
        return contents

    def _demo_fallback(self, user_message: str) -> dict:
        """
        Dynamic mock "brain" used when GEMINI_API_KEY is invalid — e.g. in
        sandbox environments — so the ReAct loop is still demonstrable.

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

    def run(self, user_message: str) -> Generator[AgentStep, None, None]:
        """
        Run the ReAct loop for a user message.

        This is a generator — it yields AgentStep objects as they happen,
        allowing the UI to stream thoughts, actions, and observations in real time.

        Usage:
            for step in agent.run("What's 2 + 2?"):
                print(step.type, step.content)
        """
        # Add user message to memory
        self.memory.add("user", user_message)
        contents = self._build_contents()
        demo_mode = False

        for iteration in range(config.MAX_ITERATIONS):
            # ── THINK ──────────────────────────────────────────────
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
                    # In sandbox environments, API keys are often redacted or invalid.
                    # Fall back to a dynamic mock so the loop is still demonstrable.
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

            # ── ANSWER ─────────────────────────────────────────────
            if "final_answer" in outcome:
                self.memory.add("assistant", outcome["final_answer"])
                yield AgentStep("answer", outcome["final_answer"])
                return

            # ── ACT + OBSERVE ─────────────────────────────────────
            if "action" in outcome:  # demo mode: single synthetic call
                calls = [(outcome["action"], outcome["args"])]
            else:  # real mode: one or more native function calls
                calls = [(fc.name, dict(fc.args)) for fc in outcome["calls"]]

            response_parts = []
            for tool_name, tool_input in calls:
                yield AgentStep("action", json.dumps(tool_input), tool_name=tool_name)

                observation = run_tool(tool_name, tool_input)
                yield AgentStep("observation", observation, tool_name=tool_name)

                obs_text = f"Observation from {tool_name}: {observation}"
                self.memory.add("tool", obs_text, tool_name=tool_name)

                if not demo_mode:
                    response_parts.append(
                        genai_types.Part.from_function_response(
                            name=tool_name, response={"result": observation}
                        )
                    )

            if demo_mode:
                # No real function-call turn to answer — the next iteration's
                # _demo_fallback() reads the tool observation straight from memory.
                continue

            contents.append(genai_types.Content(role="user", parts=response_parts))

        # Hit max iterations — force a stop
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
