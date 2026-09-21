"""
RAG Retriever Service — searches Qdrant for relevant scientific evidence.

Returns typed evidence chunks and formats them with standardized citation tags
for direct consumption by the LangGraph agent prompt.
"""

import logging
from dataclasses import dataclass
from typing import Any

from qdrant_client.http import models

from src.config import Config
from src.rag.embedder import local_embedder
from src.rag.indexer import DEFAULT_COLLECTION_NAME, get_qdrant_client

logger = logging.getLogger(__name__)


@dataclass
class EvidenceChunk:
    """A retrieved piece of scientific literature with citation metadata."""

    citation_id: str
    title: str
    authors: str
    year: int
    category: str
    topics: list[str]
    section: str
    text: str
    score: float


class EvidenceRetriever:
    """Retrieves relevant scientific evidence chunks from Qdrant."""

    def __init__(self, collection_name: str | None = None) -> None:
        self.collection_name = (
            collection_name or Config.QDRANT_COLLECTION_NAME or DEFAULT_COLLECTION_NAME
        )
        self.client = get_qdrant_client()

    def search(
        self,
        query: str,
        top_k: int = 4,
        score_threshold: float = 0.30,
        category: str | None = None,
    ) -> list[EvidenceChunk]:
        """
        Search evidence documents in Qdrant by semantic similarity.

        Args:
            query: Natural language query (e.g. "How many sets per week for hypertrophy?")
            top_k: Number of chunks to return
            score_threshold: Minimum cosine similarity score
            category: Optional filter ('training' or 'nutrition')

        Returns:
            List of EvidenceChunk objects sorted by relevance
        """
        query_vector = local_embedder.embed_query(query)

        query_filter: models.Filter | None = None
        if category:
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="category",
                        match=models.MatchValue(value=category),
                    )
                ]
            )

        response = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            limit=top_k,
            score_threshold=score_threshold,
        )

        chunks: list[EvidenceChunk] = []
        for res in response.points:
            payload: dict[str, Any] = res.payload or {}
            chunks.append(
                EvidenceChunk(
                    citation_id=payload.get("citation_id", "UNKNOWN"),
                    title=payload.get("title", ""),
                    authors=payload.get("authors", ""),
                    year=payload.get("year", 0),
                    category=payload.get("category", ""),
                    topics=payload.get("topics", []),
                    section=payload.get("section", ""),
                    text=payload.get("text", ""),
                    score=round(res.score, 3) if res.score is not None else 0.0,
                )
            )

        return chunks

    def format_evidence_for_prompt(self, chunks: list[EvidenceChunk]) -> str:
        """
        Format retrieved evidence chunks as a clean text block for the LLM prompt.
        Ensures the agent has explicit citation IDs to cite in its explanations.
        """
        if not chunks:
            return "No specific research citations retrieved for this query."

        lines = ["=== RELEVANT SCIENTIFIC EVIDENCE (Cite these when making claims) ===", ""]
        for idx, c in enumerate(chunks, 1):
            lines.append(f"[{idx}] CITATION ID: {c.citation_id}")
            lines.append(f"    Source: {c.title} ({c.authors}, {c.year})")
            lines.append(f"    Topic Focus: {', '.join(c.topics)} | Section: {c.section}")
            lines.append(f"    Content: {c.text}")
            lines.append("")

        lines.append("=== END SCIENTIFIC EVIDENCE ===")
        return "\n".join(lines)


# Global retriever instance
evidence_retriever = EvidenceRetriever()


def search_evidence_for_llm(query: str, top_k: int = 3, category: str | None = None) -> str:
    """Convenience helper to retrieve and format evidence directly for LLM prompts."""
    chunks = evidence_retriever.search(query=query, top_k=top_k, category=category)
    return evidence_retriever.format_evidence_for_prompt(chunks)
