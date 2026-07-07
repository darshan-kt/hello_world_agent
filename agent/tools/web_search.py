"""
agent/tools/web_search.py — Web Search Tool
--------------------------------------------
Lets the agent search the web for current information,
powered by DuckDuckGo (via the `ddgs` package) — free, no API key required.

For higher-quality results you can swap in Tavily (free tier):
    pip install tavily-python
    client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))
    results = client.search(query)
"""

from ddgs import DDGS
from agent.tools.registry import tool

_MAX_RESULTS = 5


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
        {"query": "Who is the prime minister of India", "result": "Narendra Modi is the Prime Minister of India..."},
    ],
)
def web_search(query: str) -> str:
    """Search the web via DuckDuckGo and return the top results."""
    query = query.strip()
    if not query:
        return "Error: no search query provided."

    try:
        results = DDGS().text(query, max_results=_MAX_RESULTS)
    except Exception as e:
        return f"Error: web search failed ({e}). Try again shortly."

    if not results:
        return f"No results found for '{query}'. Try rephrasing the query."

    lines = [f"Search results for '{query}':\n"]
    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        body = r.get("body", "").strip()
        href = r.get("href", "")
        lines.append(f"{i}. {title}\n   {body}\n   Source: {href}\n")

    return "\n".join(lines)
