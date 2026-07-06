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
"""

import re
import json
import logging
from typing import Generator, Optional

from google import genai
from google.genai import types as genai_types

import config
from agent.memory import ConversationMemory
from agent.tools.registry import run_tool, list_tools, tools_prompt

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
      - Builds the full prompt (system + tools + history + user message)
      - Runs the ReAct loop
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
        self.gen_config = genai_types.GenerateContentConfig(
            temperature=config.LLM_TEMPERATURE,
            max_output_tokens=config.MAX_TOKENS,
        )

        self.memory = ConversationMemory()
        self.name = config.AGENT_NAME
        logger.info(f"Agent '{self.name}' initialized with model '{self.model_name}'")

    def _build_system_prompt(self) -> str:
        """Combine base system prompt with tool descriptions."""
        return f"{config.SYSTEM_PROMPT}\n\n{tools_prompt()}"

    def _build_full_prompt(self, user_message: str) -> str:
        """
        Build the complete prompt string sent to the LLM.

        Structure:
          [System Prompt + Tools]
          [Conversation History]
          [Current User Message]
        """
        parts = [self._build_system_prompt(), "\n---\n"]

        # Add conversation history
        for msg in self.memory.get_history():
            if msg.role == "user":
                parts.append(f"User: {msg.content}")
            elif msg.role in ("assistant", "tool"):
                parts.append(f"Assistant: {msg.content}")

        # Add current message
        parts.append(f"\nUser: {user_message}")
        parts.append("Assistant:")

        return "\n".join(parts)

    def _parse_llm_response(self, response_text: str) -> dict:
        """
        Parse the LLM output to extract:
          - thought (reasoning)
          - action (tool name) + action_input (tool args)
          - final_answer
        """
        result = {
            "thought": "",
            "action": None,
            "action_input": {},
            "final_answer": None,
            "raw": response_text,
        }

        # Extract Thought
        thought_match = re.search(r"Thought:\s*(.+?)(?=Action:|Final Answer:|$)", response_text, re.DOTALL)
        if thought_match:
            result["thought"] = thought_match.group(1).strip()

        # Extract Final Answer
        final_match = re.search(r"Final Answer:\s*(.+)", response_text, re.DOTALL)
        if final_match:
            result["final_answer"] = final_match.group(1).strip()
            return result

        # Extract Action + Action Input
        action_match = re.search(r"Action:\s*(\w+)", response_text)
        input_match  = re.search(r"Action Input:\s*(\{.+?\}|\".+?\")", response_text, re.DOTALL)

        if action_match:
            result["action"] = action_match.group(1).strip()

        if input_match:
            raw_input = input_match.group(1).strip()
            try:
                result["action_input"] = json.loads(raw_input)
            except json.JSONDecodeError:
                # If not valid JSON, wrap as a single string argument
                result["action_input"] = {"input": raw_input.strip('"')}

        # If no action found but no final answer either, treat whole response as final answer
        if not result["action"] and not result["final_answer"]:
            result["final_answer"] = response_text.strip()

        return result

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

        for iteration in range(config.MAX_ITERATIONS):
            # ── THINK ──────────────────────────────────────────────
            prompt = self._build_full_prompt(user_message if iteration == 0 else "")
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=self.gen_config,
                )
                llm_text = response.text
            except Exception as e:
                yield AgentStep("error", f"LLM error: {e}")
                return

            parsed = self._parse_llm_response(llm_text)

            # Emit the thought
            if parsed["thought"]:
                yield AgentStep("thought", parsed["thought"])

            # ── ANSWER ─────────────────────────────────────────────
            if parsed["final_answer"]:
                self.memory.add("assistant", parsed["final_answer"])
                yield AgentStep("answer", parsed["final_answer"])
                return

            # ── ACT ────────────────────────────────────────────────
            if parsed["action"]:
                tool_name = parsed["action"]
                tool_input = parsed["action_input"]

                yield AgentStep("action", json.dumps(tool_input), tool_name=tool_name)

                # ── OBSERVE ────────────────────────────────────────
                observation = run_tool(tool_name, tool_input)
                yield AgentStep("observation", observation, tool_name=tool_name)

                # Feed observation back into the prompt as context
                obs_text = f"Observation from {tool_name}: {observation}"
                self.memory.add("tool", obs_text, tool_name=tool_name)

                # Update user_message to empty so subsequent iterations
                # build from memory context
                user_message = ""
                continue

            # No action, no answer — LLM gave something unexpected
            yield AgentStep("answer", llm_text.strip())
            self.memory.add("assistant", llm_text.strip())
            return

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
