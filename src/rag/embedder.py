"""
In-process local text embedding service using FastEmbed.

Uses 'BAAI/bge-small-en-v1.5' (384 dimensions, ONNX quantized).
- 100% local, fast in-process CPU inference
- No API keys, no network calls during generation
- Ideal for production retrieval and bulk indexing
"""

import logging
from typing import Generator

from fastembed import TextEmbedding

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "nomic-ai/nomic-embed-text-v1.5"
VECTOR_DIMENSION = 768


class LocalEmbedder:
    """Singleton-style wrapper around FastEmbed TextEmbedding."""

    _instance: "LocalEmbedder | None" = None
    _model: TextEmbedding | None = None

    def __init__(self, model_name: str = DEFAULT_MODEL_NAME) -> None:
        self.model_name = model_name
        if LocalEmbedder._model is None:
            logger.info("Initializing FastEmbed TextEmbedding model: %s", model_name)
            LocalEmbedder._model = TextEmbedding(model_name=model_name)

    @property
    def dimension(self) -> int:
        return VECTOR_DIMENSION

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed a list of text strings into vectors."""
        if not texts:
            return []
        assert LocalEmbedder._model is not None
        embeddings: Generator = LocalEmbedder._model.embed(texts)
        return [v.tolist() for v in embeddings]

    def embed_query(self, query: str) -> list[float]:
        """Embed a single search query."""
        results = self.embed_texts([query])
        return results[0]


# Global embedder instance
local_embedder = LocalEmbedder()
