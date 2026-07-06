"""
agent/tools/web_search.py — Web Search Tool
--------------------------------------------
Lets the agent search the web for current information.
Mocked here — to make it real, use SerpAPI, Tavily, or DuckDuckGo.

Real implementation (Tavily, free tier):
    pip install tavily-python
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    results = client.search(query)
"""

from agent.tools.registry import tool


# Mock knowledge base for demonstration
_MOCK_KNOWLEDGE = {
    "python":           "Python is a high-level, interpreted programming language known for its simplicity and versatility. Created by Guido van Rossum in 1991.",
    "ai agent":         "An AI agent is a system that perceives its environment, makes decisions, and takes actions to achieve goals. Uses LLMs + tools + memory + planning.",
    "react pattern":    "ReAct (Reasoning + Acting) is an agent framework where the LLM alternates between Thought, Action, and Observation steps to solve tasks.",
    "langchain":        "LangChain is a framework for building LLM applications. It provides chains, agents, memory, and tool integrations.",
    "gemini":           "Google Gemini is Google's multimodal AI model family. Gemini 2.0 Flash is fast, capable, and free-tier available via Google AI Studio.",
    "rag":              "Retrieval-Augmented Generation (RAG) combines LLMs with a retrieval system to answer questions using external knowledge bases.",
    "llm":              "Large Language Models (LLMs) are deep learning models trained on vast text data. Examples: GPT-4, Gemini, Claude, Llama.",
    "ros":              "Robot Operating System (ROS) is a flexible framework for writing robot software with libraries, tools, and conventions.",
    "robotics":         "Robotics combines AI, mechanical engineering, and computer science to build autonomous machines that interact with the physical world.",
}


@tool(
    name="web_search",
    description=(
        "Search the web for information about a topic. "
        "Use this for current events, factual questions, or anything you're unsure about."
    ),
    parameters={
        "query": {
            "type": "string",
            "description": "The search query",
        }
    },
    examples=[
        {"query": "What is Python?",    "result": "Python is a high-level programming language..."},
        {"query": "What is an AI agent","result": "An AI agent is a system that perceives..."},
    ],
)
def web_search(query: str) -> str:
    """Search for information (mocked for demo, replace with real API)."""
    query_lower = query.lower()

    # Find best matching mock result
    best_match = None
    best_score = 0
    for key, value in _MOCK_KNOWLEDGE.items():
        words = key.split()
        score = sum(1 for w in words if w in query_lower)
        if score > best_score:
            best_score = score
            best_match = value

    if best_match and best_score > 0:
        return f"Search results for '{query}':\n\n{best_match}\n\n[Source: Knowledge Base (Demo Mode)]"

    return (
        f"Search results for '{query}':\n\n"
        f"No specific results found in demo mode. "
        f"In production, this would return real web results.\n\n"
        f"💡 To enable real search: Get a free Tavily API key at https://tavily.com "
        f"and set TAVILY_API_KEY in your .env file."
    )
