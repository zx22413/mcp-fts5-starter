"""Command-line entry point: ``mcp-fts5-starter <subcommand>``.

Subcommands:

- ``serve``    — run the MCP server (reads MCP_FTS5_CORPUS / MCP_FTS5_DB env)
- ``index``    — incremental sync of a corpus directory into the index
- ``rebuild``  — wipe the index and reindex everything
- ``search``   — run a one-off query and print results
- ``list``     — page through indexed documents

Designed so a developer can verify their corpus indexes correctly before
wiring the server into Claude Code or another MCP client.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from .ingest import rebuild as rebuild_corpus
from .ingest import sync as sync_corpus
from .search import SearchDB


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="mcp-fts5-starter",
        description="MCP server template with SQLite FTS5 backend.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("serve", help="Run the MCP server (stdio transport).")

    p_index = sub.add_parser("index", help="Incrementally sync a corpus into the index.")
    _add_corpus_args(p_index)

    p_rebuild = sub.add_parser("rebuild", help="Wipe the index and reindex everything.")
    _add_corpus_args(p_rebuild)

    p_search = sub.add_parser("search", help="Run a one-off search query.")
    _add_corpus_args(p_search)
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=5)
    p_search.add_argument("--doc-type", default="")

    p_list = sub.add_parser("list", help="List indexed documents.")
    _add_corpus_args(p_list)
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--offset", type=int, default=0)
    p_list.add_argument("--doc-type", default="")

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    if args.cmd == "serve":
        from . import server

        server.main()
        return 0

    corpus = _resolve_corpus(getattr(args, "corpus", None))
    db_path = _resolve_db(getattr(args, "db", None), corpus)

    if args.cmd == "index":
        with SearchDB(db_path) as db:
            stats = sync_corpus(db, corpus)
        print(f"indexed {stats.total} doc(s): {stats.updated} updated, "
              f"{stats.skipped} unchanged, {stats.deleted} removed, {stats.failed} failed")
        return 0

    if args.cmd == "rebuild":
        with SearchDB(db_path) as db:
            stats = rebuild_corpus(db, corpus)
        print(f"rebuilt index with {stats.total} doc(s) ({stats.failed} failed)")
        return 0

    if args.cmd == "search":
        with SearchDB(db_path) as db:
            results = db.search(args.query, limit=args.limit, doc_type=args.doc_type)
        if not results:
            print(f'no matches for "{args.query}"')
            return 1
        for r in results:
            print(f"- [{r.score:.3f}] {r.title}  ({r.path})")
        return 0

    if args.cmd == "list":
        with SearchDB(db_path) as db:
            results = db.list_documents(
                doc_type=args.doc_type, limit=args.limit, offset=args.offset
            )
        if not results:
            print("no documents indexed")
            return 0
        for r in results:
            print(f"- {r.title}  ({r.path})")
        return 0

    parser.print_help(sys.stderr)
    return 2


def _add_corpus_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--corpus",
        help="Corpus directory (defaults to $MCP_FTS5_CORPUS).",
    )
    parser.add_argument(
        "--db",
        help="Path to the SQLite index file (defaults to $MCP_FTS5_DB or "
             "<corpus>/../data/index.db).",
    )


def _resolve_corpus(arg: str | None) -> Path:
    raw = arg or os.environ.get("MCP_FTS5_CORPUS")
    if not raw:
        raise SystemExit("Pass --corpus or set MCP_FTS5_CORPUS.")
    path = Path(raw).expanduser().resolve()
    if not path.exists():
        raise SystemExit(f"corpus directory does not exist: {path}")
    return path


def _resolve_db(arg: str | None, corpus: Path) -> Path:
    raw = arg or os.environ.get("MCP_FTS5_DB")
    if raw:
        return Path(raw).expanduser().resolve()
    return corpus.parent / "data" / "index.db"


if __name__ == "__main__":
    sys.exit(main())
