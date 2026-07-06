"""
main.py — CLI Entry Point for Hello Agent
------------------------------------------
Run this for a terminal-based chat session.
Great for testing without the web UI.

Usage:
    python main.py
    python main.py --message "What is 42 * 7?"
"""

import sys
import argparse
import logging
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.prompt import Prompt
from rich.style import Style
from rich import print as rprint

# Import agent (tool registration happens via agent/__init__.py)
from agent import Agent
from agent.core import AgentStep

console = Console()

# Suppress noisy logs in CLI mode
logging.basicConfig(level=logging.WARNING)


STEP_STYLES = {
    "thought":     ("💭 Thinking",     "bold violet"),
    "action":      ("⚡ Tool Call",    "bold cyan"),
    "observation": ("👁️  Observation", "bold green"),
    "answer":      ("✅ Answer",       "bold white"),
    "error":       ("❌ Error",        "bold red"),
}


def print_step(step: AgentStep) -> None:
    """Pretty-print a ReAct step to the terminal."""
    style_info = STEP_STYLES.get(step.type, ("•", "white"))
    label, style = style_info

    if step.type == "answer":
        console.print(
            Panel(
                step.content,
                title=f"[{style}]{label}[/{style}]",
                border_style="green",
                padding=(1, 2),
            )
        )
    elif step.type in ("thought", "action", "observation"):
        prefix = f"[{style}]{label}[/{style}]"
        extra = f" [dim][tool: {step.tool_name}][/dim]" if step.tool_name else ""
        console.print(f"\n  {prefix}{extra}")
        console.print(f"  [dim]{step.content}[/dim]")
    elif step.type == "error":
        console.print(f"\n  [{style}]{label}[/{style}] {step.content}")


def print_banner(agent_name: str) -> None:
    """Print the startup banner."""
    banner = Text()
    banner.append("  Hello Agent  ", style="bold white on #7c6af7")
    banner.append(f"  Agent: {agent_name}  ", style="dim")

    console.print()
    console.print(Panel(
        banner,
        subtitle="[dim]Type 'quit' to exit · 'reset' to clear memory · 'tools' to list tools[/dim]",
        border_style="#7c6af7",
        padding=(0, 2),
    ))
    console.print()


def interactive_cli(agent: Agent) -> None:
    """Run an interactive CLI chat session."""
    print_banner(agent.name)

    while True:
        try:
            user_input = Prompt.ask("[bold #7c6af7]You[/bold #7c6af7]")
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Goodbye![/dim]")
            break

        user_input = user_input.strip()

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            console.print("[dim]Goodbye![/dim]")
            break
        if user_input.lower() == "reset":
            agent.reset()
            console.print("[dim]✓ Memory cleared.[/dim]\n")
            continue
        if user_input.lower() == "tools":
            from agent.tools.registry import list_tools
            tools = list_tools()
            console.print("\n[bold]Available Tools:[/bold]")
            for name, t in tools.items():
                console.print(f"  • [cyan]{name}[/cyan]: {t.description}")
            console.print()
            continue

        console.print()
        for step in agent.run(user_input):
            print_step(step)
        console.print()


def single_message(agent: Agent, message: str) -> None:
    """Run a single message and exit (useful for scripting)."""
    console.print(f"\n[dim]Query:[/dim] {message}\n")
    for step in agent.run(message):
        print_step(step)
    console.print()


def main():
    parser = argparse.ArgumentParser(
        description="Hello Agent — ReAct AI Agent Reference",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --message "What is sqrt(144)?"
  python main.py --message "What's the weather in Tokyo?"
  python main.py --message "Remember that my name is Darshan"
        """,
    )
    parser.add_argument("--message", "-m", type=str, help="Send a single message and exit")
    parser.add_argument("--server", "-s", action="store_true", help="Start the web server instead")
    args = parser.parse_args()

    if args.server:
        import uvicorn
        import config
        console.print(f"[bold green]Starting web server at http://{config.API_HOST}:{config.API_PORT}[/bold green]")
        uvicorn.run("api.server:app", host=config.API_HOST, port=config.API_PORT, reload=True)
        return

    try:
        agent = Agent()
    except ValueError as e:
        console.print(f"[bold red]Setup Error:[/bold red] {e}")
        sys.exit(1)

    if args.message:
        single_message(agent, args.message)
    else:
        interactive_cli(agent)


if __name__ == "__main__":
    main()
