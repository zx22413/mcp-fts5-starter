"""Tokenizer abstraction.

Default: SQLite's built-in ``unicode61`` tokenizer (does CJK character-level
breaking — good enough for keyword search across Latin + Han text).

Optional: ``jieba`` for Chinese word segmentation. Install with::

    pip install mcp-fts5-starter[jieba]

Then opt in by passing ``tokenizer="jieba"`` when constructing ``SearchDB``,
or set ``MCP_FTS5_TOKENIZER=jieba`` in the environment.

Why this matters: FTS5 stores tokens, not raw text. With ``unicode61`` a query
like "agent harness" matches whole words, but Chinese phrases like "代理工具"
get split into single characters — usable, but recall suffers on multi-char
queries. ``jieba`` pre-segments Chinese into multi-character tokens before
indexing, which lifts recall for Chinese-heavy corpora at the cost of an
extra dependency and a small ingest-time overhead.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable

logger = logging.getLogger(__name__)

Tokenizer = Callable[[str], str]


def passthrough(text: str) -> str:
    """No-op tokenizer; lets FTS5 handle tokenization via its declared rule.

    Use this when the FTS5 virtual table is created with ``tokenize='unicode61'``.
    """
    return text or ""


def jieba_tokenizer() -> Tokenizer:
    """Return a jieba-based pre-tokenizer. Raises if jieba isn't installed.

    The returned function joins jieba segments with spaces so FTS5's
    whitespace-aware ``unicode61`` tokenizer can index them as discrete terms.
    """
    try:
        import jieba  # type: ignore
    except ImportError as exc:  # pragma: no cover - depends on extras
        raise RuntimeError(
            "jieba tokenizer requested but jieba is not installed. "
            "Install with: pip install mcp-fts5-starter[jieba]"
        ) from exc

    jieba.setLogLevel(logging.WARNING)

    def tokenize(text: str) -> str:
        if not text:
            return ""
        return " ".join(jieba.cut(text))

    return tokenize


def resolve(name: str | None = None) -> Tokenizer:
    """Resolve a tokenizer by name. Falls back to the env var, then passthrough.

    Names: ``unicode61`` | ``jieba``.
    """
    chosen = (name or os.environ.get("MCP_FTS5_TOKENIZER") or "unicode61").lower()
    if chosen == "jieba":
        return jieba_tokenizer()
    return passthrough
