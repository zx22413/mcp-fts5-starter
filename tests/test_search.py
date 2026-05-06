"""SearchDB end-to-end tests against an in-memory style temp index."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_fts5_starter.search import SearchDB


@pytest.fixture
def db(tmp_path: Path) -> SearchDB:
    return SearchDB(tmp_path / "index.db")


def test_upsert_and_search_returns_match(db: SearchDB) -> None:
    db.upsert(
        path="docs/intro.md",
        title="Getting Started with FTS5",
        summary="A quick intro to SQLite full-text search.",
        content="FTS5 is the recommended search module.",
        tags="sqlite fts5",
        doc_type="docs",
        created="2026-05-07",
    )
    results = db.search("FTS5")
    assert len(results) == 1
    assert results[0].path == "docs/intro.md"
    assert results[0].title == "Getting Started with FTS5"


def test_search_filters_by_doc_type(db: SearchDB) -> None:
    db.upsert(path="a.md", title="Alpha", content="search me", doc_type="notes")
    db.upsert(path="b.md", title="Beta", content="search me", doc_type="logs")

    notes_only = db.search("search", doc_type="notes")
    assert [r.path for r in notes_only] == ["a.md"]


def test_search_path_prefix_scopes_results(db: SearchDB) -> None:
    db.upsert(path="a/x.md", title="x", content="hello", doc_type="a")
    db.upsert(path="b/y.md", title="y", content="hello", doc_type="b")

    a_only = db.search("hello", path_prefix="a/")
    assert [r.path for r in a_only] == ["a/x.md"]


def test_search_empty_index_returns_empty_list(db: SearchDB) -> None:
    assert db.search("anything") == []


def test_search_falls_back_to_like_on_invalid_fts_query(db: SearchDB) -> None:
    db.upsert(path="a.md", title="Topic", content="discussion of FTS5 quirks", doc_type="doc")
    # Unbalanced quote produces a SQL parse error in FTS5 MATCH; the
    # SearchDB should silently fall back to a LIKE scan.
    results = db.search('"unbalanced')
    # No keyword matches "unbalanced", so result is empty but the call
    # must not raise.
    assert results == []


def test_list_documents_orders_by_created_desc(db: SearchDB) -> None:
    db.upsert(path="old.md", title="old", content="x", created="2026-01-01")
    db.upsert(path="new.md", title="new", content="x", created="2026-05-07")

    listed = db.list_documents()
    assert [r.path for r in listed] == ["new.md", "old.md"]


def test_delete_removes_from_index(db: SearchDB) -> None:
    db.upsert(path="x.md", title="x", content="hello", doc_type="d")
    assert db.search("hello")
    db.delete("x.md")
    assert db.search("hello") == []


class _FakeEmbedder:
    """Deterministic 3-D embedder for RRF fusion tests.

    Returns a fixed vector based on whether the input contains the keyword
    'cat' or 'dog'. Lets us assert that vector hits boost a doc that BM25
    also ranks, and pull in a doc that BM25 misses.
    """

    def embed(self, texts: list[str]) -> list[list[float]]:
        out: list[list[float]] = []
        for t in texts:
            t_lower = t.lower()
            if "cat" in t_lower:
                out.append([1.0, 0.0, 0.0])
            elif "dog" in t_lower:
                out.append([0.0, 1.0, 0.0])
            else:
                out.append([0.0, 0.0, 1.0])
        return out


def test_search_with_embedder_fuses_results(tmp_path: Path) -> None:
    db = SearchDB(tmp_path / "index.db", embedder=_FakeEmbedder())
    db.upsert(path="cats.md", title="cats", content="all about cats", doc_type="d")
    db.upsert(path="dogs.md", title="dogs", content="all about dogs", doc_type="d")
    db.upsert(path="other.md", title="other", content="unrelated content", doc_type="d")

    # BM25 alone wouldn't hit dogs.md from a "cat" query; the fake embedder
    # gives "cat" a vector that perfectly matches cats.md only, so RRF
    # should still surface cats.md first.
    results = db.search("cat")
    assert results[0].path == "cats.md"
