"""
Interactive Test Runner for Science-Fit LangGraph Agent.

Tests the compiled StateGraph against test user #1 (created via create_test_user.py).

Usage:
    python scripts/test_agent.py
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Ensure UTF-8 output on Windows console
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Suppress verbose DB logs
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from langchain_core.messages import HumanMessage
from rich.console import Console
from rich.panel import Panel

from sqlalchemy import select
from src.database import AsyncSessionLocal
from src.models import User
from src.agent.graph import fitness_agent_app

console = Console()


async def run_agent_test():
    console.print(Panel.fit("[bold green]Science-Fit LangGraph Agent Test Runner[/bold green]"))

    # Dynamically find the test user ID
    async with AsyncSessionLocal() as session:
        stmt = select(User.id).where(User.email == "test@sciencefit.dev").limit(1)
        res = await session.execute(stmt)
        user_id = res.scalar_one_or_none() or 3

    console.print(f"[dim]Using test user ID: {user_id}[/dim]")

    # thread_id identifies the conversation session in LangGraph's checkpointer
    config = {"configurable": {"thread_id": f"test-user-session-{user_id}"}}

    # Turn 1: Workout & Volume Review
    query_1 = "How is my weekly training volume looking? Am I doing enough sets for legs and back?"
    console.print(f"\n[bold cyan]User Turn 1:[/bold cyan] {query_1}\n")

    initial_input = {
        "messages": [HumanMessage(content=query_1)],
        "user_id": user_id,
    }

    try:
        result_1 = await fitness_agent_app.ainvoke(initial_input, config=config)

        console.print(f"[bold yellow]Classified Intent:[/bold yellow] {result_1.get('intent')}")
        console.print(f"[bold yellow]Retrieved Evidence Chunks:[/bold yellow] {len(result_1.get('retrieved_evidence', []))}")
        
        last_message = result_1["messages"][-1]
        console.print(Panel(last_message.content, title="[bold blue]Science-Fit Coach Response[/bold blue]"))

    except Exception as e:
        console.print(f"[bold red]Error running agent on Turn 1:[/bold red] {e}")
        return

    # Turn 2: Multi-Turn Nutrition Inquiry (Tests MemorySaver Checkpointer)
    query_2 = "What are my daily calorie and protein targets, and what study supports my protein intake?"
    console.print(f"\n[bold cyan]User Turn 2 (Testing Memory):[/bold cyan] {query_2}\n")

    followup_input = {
        "messages": [HumanMessage(content=query_2)],
    }

    try:
        result_2 = await fitness_agent_app.ainvoke(followup_input, config=config)
        console.print(f"[bold yellow]Classified Intent:[/bold yellow] {result_2.get('intent')}")
        
        last_message_2 = result_2["messages"][-1]
        console.print(Panel(last_message_2.content, title="[bold blue]Science-Fit Coach Response (Turn 2)[/bold blue]"))

    except Exception as e:
        console.print(f"[bold red]Error running agent on Turn 2:[/bold red] {e}")

    # Turn 3: Tool Invocation (Hypothetical Macro Calculation)
    query_3 = "What would my calories and macros look like if I weighed 75 kg and wanted to do a cut with moderate activity?"
    console.print(f"\n[bold cyan]User Turn 3 (Testing Tool Invocation):[/bold cyan] {query_3}\n")

    tool_test_input = {
        "messages": [HumanMessage(content=query_3)],
    }

    try:
        result_3 = await fitness_agent_app.ainvoke(tool_test_input, config=config)
        console.print(f"[bold yellow]Classified Intent:[/bold yellow] {result_3.get('intent')}")
        
        last_message_3 = result_3["messages"][-1]
        console.print(Panel(last_message_3.content, title="[bold blue]Science-Fit Coach Response (Turn 3 - Tool Invoked)[/bold blue]"))

    except Exception as e:
        console.print(f"[bold red]Error running agent on Turn 3:[/bold red] {e}")


if __name__ == "__main__":
    asyncio.run(run_agent_test())
