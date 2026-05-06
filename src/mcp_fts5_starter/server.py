"""MCP server exposing four generic tools over a FTS5 index.

Tools:

- ``search(query, limit, doc_type)`` — BM25 (or BM25+vector RRF if an
  embedder is configured) over the corpus.
- ``list(doc_type, limit, offset)`` — page through indexed documents.
- ``read(path)`` — return a single document's raw content.
- ``index()`` — incrementally re-sync the corpus directory into the index.

Configuration via env vars:

- ``MCP_FTS5_CORPUS`` — directory of markdown files to index (required)
- ``MCP_FTS5_DB`` — path to the SQLite index file (default: ``data/index.db``
  alongside the corpus)
- ``MCP_FTS5_TOKENIZER`` — ``unicode61`` (default) or ``jieba``
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from .ingest import sync as ingest_sync
from .search import SearchDB

logger = logging.getLogger(__name__)

mcp = FastMCP("mcp-fts5-starter")


def _corpus_dir() -> Path:
    raw = os.environ.get("MCP_FTS5_CORPUS")
    if not raw:
        raise RuntimeError(
            "MCP_FTS5_CORPUS is not set. Point it at the directory you want to index."
        )
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"corpus directory does not exist: {path}")
    return path


def _db_path() -> Path:
    raw = os.environ.get("MCP_FTS5_DB")
    if raw:
        return Path(raw).expanduser().resolve()
    return _corpus_dir().parent / "data" / "index.db"


def _open_db() -> SearchDB:
    return SearchDB(_db_path())


@mcp.tool()
def search(query: str, limit: int = 5, doc_type: str = "") -> str:
    """Search the indexed corpus.

    Args:
        query: search keywords or phrase
        limit: max results to return (default 5)
        doc_type: optional filter on document type (matches the parent folder
            name of each indexed file unless overridden by a custom extractor)
    """
    with _open_db() as db:
        results = db.search(query, limit=limit, doc_type=doc_type)
    if not results:
        scope = f" (doc_type={doc_type})" if doc_type else ""
        return f'No matches for "{query}"{scope}.'

    lines = [f"Found {len(results)} result(s):\n"]
    for r in results:
        block = (
            f"**{r.title}** [{r.type or 'doc'}]\n"
            f"path: {r.path}\n"
            f"tags: {r.tags or '-'}\n"
            f"summary: {r.summary[:200] or '-'}\n"
        )
        snippet = _snippet(r.path, query)
        if snippet:
            block += f"snippet:\n{snippet}\n"
        lines.append(block)
    return "\n---\n".join(lines)


@mcp.tool()
def list(doc_type: str = "", limit: int = 50, offset: int = 0) -> str:
    """List indexed documents.

    Args:
        doc_type: optional filter on document type
        limit: page size (default 50)
        offset: page offset (default 0)
    """
    with _open_db() as db:
        results = db.list_documents(doc_type=doc_type, limit=limit, offset=offset)
    if not results:
        return "No documents indexed."
    lines = [f"{len(results)} document(s):\n"]
    for r in results:
        lines.append(f"- **{r.title}** [{r.type or 'doc'}] — {r.path}")
    return "\n".join(lines)


@mcp.tool()
def read(path: str) -> str:
    """Read the raw content of a single indexed document.

    Args:
        path: the indexed path (as shown by ``search`` or ``list``)
    """
    file = _corpus_dir() / path
    if not file.exists() or not file.is_file():
        return f"Not found: {path}"
    return file.read_text(encoding="utf-8", errors="ignore")


@mcp.tool()
def index() -> str:
    """Re-sync the corpus directory into the FTS5 index. Incremental by mtime."""
    with _open_db() as db:
        stats = ingest_sync(db, _corpus_dir())
    return (
        f"Indexed {stats.total} document(s): "
        f"{stats.updated} updated, {stats.skipped} unchanged, "
        f"{stats.deleted} removed, {stats.failed} failed."
    )


def _snippet(rel_path: str, query: str, *, lines_around: int = 2, max_matches: int = 2) -> str:
    """Pull a few lines of context around the first matches of ``query``.

    Cheap heuristic: split the query into words >1 char and scan for any
    occurrence. Skips frontmatter so the snippet is body content.
    """
    try:
        file = _corpus_dir() / rel_path
        text = file.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

    body_lines = text.splitlines()
    start = 0
    if body_lines and body_lines[0].strip() == "---":
        for i in range(1, len(body_lines)):
            if body_lines[i].strip() == "---":
                start = i + 1
                break

    words = [w.lower() for w in re.split(r"\s+", query) if len(w) > 1]
    if not words:
        return ""

    snippets: list[str] = []
    used: set[int] = set()
    for i in range(start, len(body_lines)):
        if not any(w in body_lines[i].lower() for w in words):
            continue
        lo = max(start, i - lines_around)
        hi = min(len(body_lines), i + lines_around + 1)
        if any(lo <= u <= hi for u in used):
            continue
        snippets.append("\n".join(f"  {body_lines[j]}" for j in range(lo, hi)))
        used.update(range(lo, hi))
        if len(snippets) >= max_matches:
            break
    return "\n  ...\n".join(snippets)


_VALID_TRANSPORTS = ("stdio", "sse", "streamable-http")


def main(
    transport: str = "stdio",
    *,
    host: str | None = None,
    port: int | None = None,
) -> None:
    """Entry point used by ``mcp-fts5-starter serve``.

    ``stdio`` (default) is what Claude Code / Claude Desktop spawn locally.
    ``sse`` and ``streamable-http`` bind a TCP listener — pass ``host`` and
    ``port`` to override the FastMCP defaults (127.0.0.1:8000).
    """
    if transport not in _VALID_TRANSPORTS:
        raise ValueError(
            f"unknown transport {transport!r}; expected one of {_VALID_TRANSPORTS}"
        )
    if host is not None:
        mcp.settings.host = host
    if port is not None:
        mcp.settings.port = port
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
