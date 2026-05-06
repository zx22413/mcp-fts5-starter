"""One-shot demo: rebuild ``data/sample/index.db`` from ``data/sample/`` and
run a few representative searches so a new user can see the starter work
end-to-end with one command.

Run from anywhere::

    python scripts/build-sample.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mcp_fts5_starter.ingest import rebuild  # noqa: E402
from mcp_fts5_starter.search import SearchDB  # noqa: E402


CORPUS = REPO_ROOT / "data" / "sample"
DB_PATH = REPO_ROOT / "data" / "sample" / "index.db"

DEMO_QUERIES: list[tuple[str, str]] = [
    ("BM25 weights", ""),
    ("hybrid search", ""),
    ("tokenizer", "notes"),
]


def main() -> int:
    if not CORPUS.exists():
        print(f"corpus not found: {CORPUS}", file=sys.stderr)
        return 1

    if DB_PATH.exists():
        DB_PATH.unlink()

    print(f"Rebuilding index at {DB_PATH.relative_to(REPO_ROOT)}")
    with SearchDB(DB_PATH) as db:
        stats = rebuild(db, CORPUS)
        print(
            f"  indexed {stats.total} doc(s): "
            f"{stats.updated} written, {stats.failed} failed\n"
        )

        for query, doc_type in DEMO_QUERIES:
            scope = f" [doc_type={doc_type}]" if doc_type else ""
            print(f"Query: {query!r}{scope}")
            results = db.search(query, limit=3, doc_type=doc_type)
            if not results:
                print("  (no matches)\n")
                continue
            for r in results:
                print(f"  - {r.title:<32}  {r.path}")
            print()

    print("Tip: launch the MCP server against this corpus with:")
    print("  MCP_FTS5_CORPUS=data/sample MCP_FTS5_DB=data/sample/index.db \\")
    print("    mcp-fts5-starter serve")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
