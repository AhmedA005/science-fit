"""
Seed script: Index scientific research papers into Qdrant vector database.

Reads all markdown papers from knowledge/ directory, generates vector embeddings
using nomic-embed-text, and upserts them into Qdrant collection.

Usage:
    python scripts/seed_knowledge.py
"""

import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from rich.console import Console
from rich.panel import Panel

from src.rag.indexer import index_knowledge_base

console = Console()

def main():
    console.print(Panel.fit("[bold green]Science-Fit Knowledge Base Indexer (Qdrant)[/bold green]"))
    try:
        total = index_knowledge_base()
        console.print(f"[bold green]✔ Successfully indexed {total} evidence chunks into Qdrant![/bold green]")
    except Exception as e:
        console.print(f"[bold red]✘ Failed to index knowledge base:[/bold red] {e}")
        console.print("[dim]Ensure Qdrant is running (`docker compose up -d qdrant`)[/dim]")

if __name__ == "__main__":
    main()
