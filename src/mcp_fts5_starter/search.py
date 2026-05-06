"""SearchDB — the index, plus a few small APIs.

This module owns the SQLite connection and the public read/write API:

- ``upsert`` writes a single document (used by tests and the MCP ``index`` tool).
- ``delete`` removes a document by path.
- ``search`` runs BM25 against the FTS5 index, optionally fused with vector
  search via Reciprocal Rank Fusion when an Embedder is configured.
- ``list_documents`` enumerates indexed paths for the MCP ``list`` tool.

Path semantics: documents are addressed by an opaque string ``path``. Ingest
typically uses a path relative to the corpus root, but you can use any stable
identifier (URL, UUID, etc.) — the index doesn't care.
"""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import schema
from .embedding import Embedder, blob_to_vec, cosine_similarity, vec_to_blob
from .tokenizer import Tokenizer
from .tokenizer import resolve as resolve_tokenizer

logger = logging.getLogger(__name__)

# Reciprocal Rank Fusion constant. 60 is the value from the original RRF
# paper and works well in practice — it's only worth tuning if you have
# evaluation data showing a clear win.
RRF_K = 60

# Vector similarity floor: matches below this are treated as noise and
# excluded from the fused ranking. Tune to your embedder; 0.55 is a safe
# default for most off-the-shelf embedders.
VEC_MIN_SIM = 0.55


@dataclass(frozen=True)
class SearchResult:
    path: str
    title: str
    summary: str
    tags: str
    type: str
    created: str
    score: float


class SearchDB:
    """Thin wrapper around the FTS5 index. Safe to instantiate per process."""

    def __init__(
        self,
        db_path: str | Path,
        *,
        tokenizer: Tokenizer | str | None = None,
        embedder: Embedder | None = None,
    ) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn: sqlite3.Connection = schema.connect(self.db_path)
        self._tokenize: Tokenizer = (
            tokenizer if callable(tokenizer) else resolve_tokenizer(tokenizer)
        )
        self.embedder = embedder

    # ── write API ──────────────────────────────────────────────────────

    def upsert(
        self,
        *,
        path: str,
        title: str = "",
        summary: str = "",
        content: str = "",
        tags: str = "",
        doc_type: str = "",
        created: str = "",
        mtime: float | None = None,
        commit: bool = True,
    ) -> None:
        """Insert or replace a single document.

        ``tags`` is a free-form string — space- or pipe-delimited works fine.
        ``mtime`` is optional metadata used by ingest for incremental syncs.

        Set ``commit=False`` when calling in a tight loop and call
        :meth:`commit` once at the end. The ingest pipeline does this so
        a 10k-doc rebuild costs one fsync, not 10k.
        """
        tok = self._tokenize
        self.conn.execute("DELETE FROM notes_fts WHERE path = ?", (path,))
        self.conn.execute(
            "INSERT INTO notes_fts(path, title, summary, content, tags, type, created)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (path, tok(title), tok(summary), tok(content), tok(tags), doc_type, created),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO notes_display(path, title, summary, tags_raw)"
            " VALUES (?, ?, ?, ?)",
            (path, title, summary, tags),
        )
        if mtime is not None:
            self.conn.execute(
                "INSERT OR REPLACE INTO notes_meta(path, mtime) VALUES (?, ?)",
                (path, mtime),
            )

        if self.embedder is not None:
            embed_input = (title + " " + summary).strip() or content
            if embed_input:
                try:
                    vectors = self.embedder.embed([embed_input])
                except Exception as exc:  # noqa: BLE001
                    logger.warning("embedder failed for %s: %s", path, exc)
                    vectors = []
                if vectors and vectors[0]:
                    self.conn.execute(
                        "INSERT OR REPLACE INTO notes_vec(path, embedding) VALUES (?, ?)",
                        (path, vec_to_blob(vectors[0])),
                    )

        if commit:
            self.conn.commit()

    def delete(self, path: str, *, commit: bool = True) -> None:
        for table in ("notes_fts", "notes_meta", "notes_display", "notes_vec"):
            self.conn.execute(f"DELETE FROM {table} WHERE path = ?", (path,))
        if commit:
            self.conn.commit()

    def commit(self) -> None:
        """Flush pending writes. Call after a batch of ``upsert(..., commit=False)``."""
        self.conn.commit()

    def known_paths(self) -> dict[str, float]:
        """Return ``path -> mtime`` for everything currently indexed."""
        return {row[0]: row[1] for row in self.conn.execute("SELECT path, mtime FROM notes_meta")}

    def list_documents(
        self, *, doc_type: str = "", limit: int = 50, offset: int = 0
    ) -> list[SearchResult]:
        """List indexed documents, newest first by ``created``."""
        if doc_type:
            cursor = self.conn.execute(
                """
                SELECT f.path, COALESCE(d.title, f.title), COALESCE(d.summary, f.summary),
                       COALESCE(d.tags_raw, f.tags), f.type, f.created
                FROM notes_fts f
                LEFT JOIN notes_display d ON f.path = d.path
                WHERE f.type = ?
                ORDER BY f.created DESC, f.path
                LIMIT ? OFFSET ?
                """,
                (doc_type, limit, offset),
            )
        else:
            cursor = self.conn.execute(
                """
                SELECT f.path, COALESCE(d.title, f.title), COALESCE(d.summary, f.summary),
                       COALESCE(d.tags_raw, f.tags), f.type, f.created
                FROM notes_fts f
                LEFT JOIN notes_display d ON f.path = d.path
                ORDER BY f.created DESC, f.path
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
        return [
            SearchResult(
                path=row[0],
                title=row[1] or "",
                summary=row[2] or "",
                tags=row[3] or "",
                type=row[4] or "",
                created=row[5] or "",
                score=0.0,
            )
            for row in cursor
        ]

    # ── read API ───────────────────────────────────────────────────────

    def search(
        self,
        query: str,
        *,
        limit: int = 5,
        doc_type: str = "",
        path_prefix: str = "",
    ) -> list[SearchResult]:
        """BM25 search, optionally fused with dense-vector search via RRF."""
        fts = self._search_fts(query, limit=limit * 2, doc_type=doc_type, path_prefix=path_prefix)
        if self.embedder is None:
            return fts[:limit]

        vec = self._search_vec(query, limit=limit * 2, doc_type=doc_type, path_prefix=path_prefix)
        if not vec:
            return fts[:limit]
        return self._rrf_merge(fts, vec, limit)

    def _search_fts(
        self,
        query: str,
        *,
        limit: int,
        doc_type: str,
        path_prefix: str,
    ) -> list[SearchResult]:
        tokenized = self._tokenize(query)
        clauses: list[str] = []
        params: list[object] = [tokenized]
        if doc_type:
            clauses.append("AND f.type = ?")
            params.append(doc_type)
        if path_prefix:
            clauses.append("AND f.path LIKE ?")
            params.append(f"{path_prefix}%")
        params.append(limit)
        where_extra = " ".join(clauses)
        sql = f"""
            SELECT f.path,
                   COALESCE(d.title, f.title) AS title,
                   COALESCE(d.summary, f.summary) AS summary,
                   COALESCE(d.tags_raw, f.tags) AS tags,
                   f.type, f.created,
                   bm25(notes_fts, {schema.BM25_WEIGHTS}) AS rank
            FROM notes_fts f
            LEFT JOIN notes_display d ON f.path = d.path
            WHERE notes_fts MATCH ? {where_extra}
            ORDER BY rank
            LIMIT ?
        """
        try:
            cursor = self.conn.execute(sql, params)
        except sqlite3.OperationalError:
            # Malformed FTS5 query (e.g. user typed an unbalanced quote).
            # Fall back to a LIKE scan so the tool stays usable.
            return self._search_like(
                query, limit=limit, doc_type=doc_type, path_prefix=path_prefix
            )

        return [
            SearchResult(
                path=row[0],
                title=row[1] or "",
                summary=row[2] or "",
                tags=row[3] or "",
                type=row[4] or "",
                created=row[5] or "",
                score=row[6],
            )
            for row in cursor
        ]

    def _search_vec(
        self,
        query: str,
        *,
        limit: int,
        doc_type: str,
        path_prefix: str,
    ) -> list[SearchResult]:
        if self.embedder is None:
            return []
        try:
            vectors = self.embedder.embed([query])
        except Exception as exc:  # noqa: BLE001
            logger.warning("embedder failed on query: %s", exc)
            return []
        if not vectors or not vectors[0]:
            return []
        query_vec = vectors[0]

        clauses: list[str] = []
        params: list[object] = []
        if doc_type:
            clauses.append("f.type = ?")
            params.append(doc_type)
        if path_prefix:
            clauses.append("v.path LIKE ?")
            params.append(f"{path_prefix}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""

        rows = self.conn.execute(
            f"""
            SELECT v.path, v.embedding,
                   COALESCE(d.title, '') AS title,
                   COALESCE(d.summary, '') AS summary,
                   COALESCE(d.tags_raw, f.tags) AS tags,
                   f.type, f.created
            FROM notes_vec v
            LEFT JOIN notes_display d ON v.path = d.path
            LEFT JOIN notes_fts f ON v.path = f.path
            {where}
            """,
            params,
        ).fetchall()

        scored: list[SearchResult] = []
        query_dim = len(query_vec)
        for row in rows:
            vec = blob_to_vec(row[1])
            if len(vec) != query_dim:
                # Stored vector has a different dim than the current query
                # embedder. Probably a misconfigured index. Skip loudly so the
                # operator notices instead of silently truncating with zip().
                logger.warning(
                    "vec dim mismatch (stored=%d, query=%d) at path=%s — re-index needed",
                    len(vec),
                    query_dim,
                    row[0],
                )
                continue
            sim = cosine_similarity(query_vec, vec)
            if sim < VEC_MIN_SIM:
                continue
            scored.append(
                SearchResult(
                    path=row[0],
                    title=row[2],
                    summary=row[3],
                    tags=row[4] or "",
                    type=row[5] or "",
                    created=row[6] or "",
                    score=sim,
                )
            )
        scored.sort(key=lambda r: r.score, reverse=True)
        return scored[:limit]

    def _search_like(
        self,
        query: str,
        *,
        limit: int,
        doc_type: str,
        path_prefix: str,
    ) -> list[SearchResult]:
        clauses = [
            "(f.title LIKE ? OR f.summary LIKE ? OR f.content LIKE ? OR f.tags LIKE ?)"
        ]
        params: list[object] = [f"%{query}%"] * 4
        if doc_type:
            clauses.append("f.type = ?")
            params.append(doc_type)
        if path_prefix:
            clauses.append("f.path LIKE ?")
            params.append(f"{path_prefix}%")
        params.append(limit)
        where = " AND ".join(clauses)
        cursor = self.conn.execute(
            f"""
            SELECT f.path, COALESCE(d.title, f.title), COALESCE(d.summary, f.summary),
                   COALESCE(d.tags_raw, f.tags), f.type, f.created
            FROM notes_fts f
            LEFT JOIN notes_display d ON f.path = d.path
            WHERE {where}
            LIMIT ?
            """,
            params,
        )
        return [
            SearchResult(
                path=row[0],
                title=row[1] or "",
                summary=row[2] or "",
                tags=row[3] or "",
                type=row[4] or "",
                created=row[5] or "",
                score=0.0,
            )
            for row in cursor
        ]

    @staticmethod
    def _rrf_merge(
        fts_results: list[SearchResult],
        vec_results: list[SearchResult],
        limit: int,
    ) -> list[SearchResult]:
        rrf_scores: dict[str, float] = {}
        result_map: dict[str, SearchResult] = {}

        for rank, r in enumerate(fts_results):
            rrf_scores[r.path] = rrf_scores.get(r.path, 0.0) + 1.0 / (RRF_K + rank + 1)
            result_map[r.path] = r
        for rank, r in enumerate(vec_results):
            rrf_scores[r.path] = rrf_scores.get(r.path, 0.0) + 1.0 / (RRF_K + rank + 1)
            result_map.setdefault(r.path, r)

        sorted_paths = sorted(rrf_scores, key=lambda p: rrf_scores[p], reverse=True)
        merged: list[SearchResult] = []
        for path in sorted_paths[:limit]:
            base = result_map[path]
            merged.append(
                SearchResult(
                    path=base.path,
                    title=base.title,
                    summary=base.summary,
                    tags=base.tags,
                    type=base.type,
                    created=base.created,
                    score=rrf_scores[path],
                )
            )
        return merged

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> SearchDB:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
