"""
Knowledge Base Indexer — chunks scientific markdown documents and indexes them in Qdrant.

Uses:
- FastEmbed nomic-ai/nomic-embed-text-v1.5 (768-dimensional vectors)
- Qdrant collection: 'science_fit_evidence'
- Header-based semantic markdown chunking (preserves citation metadata on each chunk)
"""

import logging
import re
import uuid
from pathlib import Path
from typing import Any

import yaml
from qdrant_client import QdrantClient
from qdrant_client.http import models

from src.config import Config
from src.rag.embedder import local_embedder

logger = logging.getLogger(__name__)

DEFAULT_COLLECTION_NAME = "science_fit_evidence"


def get_qdrant_client() -> QdrantClient:
    """Instantiate a Qdrant client from Config."""
    host = Config.QDRANT_HOST or "localhost"
    port = Config.QDRANT_PORT or 6333
    return QdrantClient(host=host, port=port, check_compatibility=False)


def parse_markdown_document(file_path: Path) -> tuple[dict[str, Any], list[dict[str, str]]]:
    """
    Parse a scientific markdown document with YAML frontmatter.
    Splits content by '## ' (H2 sections) into structured chunks.
    """
    text = file_path.read_text(encoding="utf-8-sig")

    # Extract YAML frontmatter between '---' markers
    frontmatter: dict[str, Any] = {}
    content = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            frontmatter = yaml.safe_load(parts[1]) or {}
            content = parts[2].strip()

    # Split content by markdown H2 sections (## Section Name)
    section_pattern = re.compile(r"^##\s+(.+)$", re.MULTILINE)
    matches = list(section_pattern.finditer(content))

    chunks: list[dict[str, str]] = []

    if not matches:
        # Fallback: whole body is one chunk
        chunks.append({"section": "Main", "text": content.strip()})
    else:
        for i, match in enumerate(matches):
            section_title = match.group(1).strip()
            start_pos = match.end()
            end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            section_body = content[start_pos:end_pos].strip()

            if section_body:
                # Combine section header and text for semantic completeness
                chunk_text = f"Section: {section_title}\n\n{section_body}"
                chunks.append({"section": section_title, "text": chunk_text})

    return frontmatter, chunks


def index_knowledge_base(
    knowledge_dir: Path | None = None,
    collection_name: str | None = None,
    recreate: bool = False,
) -> int:
    """
    Read all markdown files in knowledge_dir, embed sections, and index in Qdrant.

    Returns the total number of chunks indexed.
    """
    client = get_qdrant_client()
    target_collection = collection_name or Config.QDRANT_COLLECTION_NAME or DEFAULT_COLLECTION_NAME
    base_dir = knowledge_dir or Config.KNOWLEDGE_BASE_DIR

    logger.info("Connecting to Qdrant for collection '%s'...", target_collection)

    # Verify or create collection
    existing_collections = [c.name for c in client.get_collections().collections]
    if recreate or target_collection not in existing_collections:
        if target_collection in existing_collections:
            client.delete_collection(collection_name=target_collection)
        client.create_collection(
            collection_name=target_collection,
            vectors_config=models.VectorParams(
                size=local_embedder.dimension,
                distance=models.Distance.COSINE,
            ),
        )
        logger.info("Created collection '%s' with dim=%d", target_collection, local_embedder.dimension)

    # Discover markdown files
    md_files = sorted(base_dir.glob("*.md"))
    if not md_files:
        logger.warning("No markdown files found in %s", base_dir)
        return 0

    total_chunks = 0
    points_to_upsert: list[models.PointStruct] = []

    for md_file in md_files:
        frontmatter, chunks = parse_markdown_document(md_file)
        citation_id = frontmatter.get("citation_id", md_file.stem)
        title = frontmatter.get("title", "")
        authors = frontmatter.get("authors", "")
        year = frontmatter.get("year", 0)
        category = frontmatter.get("category", "general")
        topics = frontmatter.get("topics", [])
        evidence_grade = frontmatter.get("evidence_grade", "expert_consensus")

        texts = [c["text"] for c in chunks]
        embeddings = local_embedder.embed_texts(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{citation_id}::{chunk['section']}"))
            payload = {
                "citation_id": citation_id,
                "title": title,
                "authors": authors,
                "year": year,
                "category": category,
                "topics": topics,
                "evidence_grade": evidence_grade,
                "section": chunk["section"],
                "text": chunk["text"],
                "source_file": md_file.name,
            }
            points_to_upsert.append(
                models.PointStruct(
                    id=chunk_id,
                    vector=embedding,
                    payload=payload,
                )
            )
            total_chunks += 1

    if points_to_upsert:
        client.upsert(
            collection_name=target_collection,
            points=points_to_upsert,
        )
        logger.info("Successfully indexed %d chunks across %d papers.", total_chunks, len(md_files))

    return total_chunks
