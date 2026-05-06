"""Optional embedding layer.

The starter ships with **no embedding provider**. BM25 alone is enough for
most small-to-medium corpora. If you want hybrid retrieval (BM25 + dense
vectors fused with RRF), implement the ``Embedder`` protocol below and pass
an instance to ``SearchDB(..., embedder=YourEmbedder())``.

Why a Protocol instead of a plug-in registry: it keeps the dependency
surface zero and lets you wire a real embedder (Gemini, OpenAI, sentence-
transformers, Ollama, etc.) without modifying this package.

Example::

    from mcp_fts5_starter.embedding import Embedder

    class GeminiEmbedder:
        def __init__(self, api_key: str) -> None:
            ...

        def embed(self, texts: list[str]) -> list[list[float]]:
            ...  # call your provider, return one vector per text

    db = SearchDB("data/index.db", embedder=GeminiEmbedder(api_key=...))
"""

from __future__ import annotations

import struct
from typing import Protocol


class Embedder(Protocol):
    """Implement this Protocol to wire in a vector backend.

    Implementations must return one vector per input text, in the same order.
    Vectors must all have the same dimensionality across calls — the schema
    stores them as packed float32 blobs and assumes a stable dim per index.
    """

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def vec_to_blob(vec: list[float]) -> bytes:
    """Pack a float vector as little-endian float32 bytes."""
    return struct.pack(f"<{len(vec)}f", *vec)


def blob_to_vec(blob: bytes) -> list[float]:
    """Unpack a stored blob back into a float list."""
    n = len(blob) // 4
    return list(struct.unpack(f"<{n}f", blob))


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Cosine similarity between two equal-length vectors. 0.0 on zero norm."""
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(x * x for x in b) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)
