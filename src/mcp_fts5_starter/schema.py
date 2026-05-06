"""FTS5 schema bootstrap.

Three tables:

- ``notes_fts``  — the FTS5 virtual table itself; stores tokenized text used
  for matching and ranking. Tokens are written by ingest, never read by
  callers (you read from ``notes_display`` instead).
- ``notes_meta`` — per-document mtime tracking so ingest can do incremental
  syncs (skip files that haven't changed since the last index pass).
- ``notes_display`` — original (un-tokenized) title/summary/tags. We store
  these separately because, with a pre-tokenizer like jieba, the FTS5
  columns hold space-delimited segments that look ugly in search results.

BM25 column weights are tuned for note-style content:
title (10) > tags (8) > summary (5) > content (1). path/type/created
don't participate in ranking. Override ``BM25_WEIGHTS`` to taste.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

# title, tags, summary, content weights — path/type/created get 0.
BM25_WEIGHTS = "0, 10, 5, 1, 8, 0, 0"


def connect(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection and ensure the schema exists."""
    conn = sqlite3.connect(str(db_path))
    _create_tables(conn)
    return conn


def _create_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS notes_fts USING fts5(
            path, title, summary, content, tags, type, created,
            tokenize='unicode61'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notes_meta(
            path TEXT PRIMARY KEY,
            mtime REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notes_display(
            path TEXT PRIMARY KEY,
            title TEXT DEFAULT '',
            summary TEXT DEFAULT '',
            tags_raw TEXT DEFAULT ''
        )
        """
    )
    # Optional embedding side-table — created up-front so the schema is stable
    # even when no embedder is configured. Stays empty until you plug one in.
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS notes_vec(
            path TEXT PRIMARY KEY,
            embedding BLOB
        )
        """
    )
    conn.commit()
