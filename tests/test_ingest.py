"""Ingest pipeline tests against a temp corpus directory."""

from __future__ import annotations

from pathlib import Path

import pytest

from mcp_fts5_starter.ingest import default_extractor, rebuild, sync
from mcp_fts5_starter.search import SearchDB


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    (root / "notes").mkdir()
    (root / "notes" / "first.md").write_text(
        """---
title: First Note
created: 2026-05-01
tags:
  - example
  - intro
---

## Summary

The first note in our corpus.

## Body

Some content with a [[wikilink]] and another [[topic]].
""",
        encoding="utf-8",
    )
    (root / "notes" / "second.md").write_text(
        """---
title: Second Note
created: 2026-05-02
---

Body without a Summary heading. First paragraph becomes the summary.
""",
        encoding="utf-8",
    )
    return root


def test_default_extractor_pulls_summary_section(corpus: Path) -> None:
    file = corpus / "notes" / "first.md"
    doc = default_extractor(file, corpus)
    assert doc.path == "notes/first.md"
    assert doc.title == "First Note"
    assert doc.summary.startswith("The first note")
    assert doc.doc_type == "notes"
    assert "example" in doc.tags
    assert "wikilink" in doc.tags  # body wikilinks merged in


def test_default_extractor_falls_back_to_first_paragraph(corpus: Path) -> None:
    doc = default_extractor(corpus / "notes" / "second.md", corpus)
    assert doc.summary.startswith("Body without a Summary")


def test_sync_indexes_corpus(tmp_path: Path, corpus: Path) -> None:
    db = SearchDB(tmp_path / "index.db")
    stats = sync(db, corpus)
    assert stats.total == 2
    assert stats.updated == 2
    assert stats.skipped == 0

    results = db.search("first note")
    assert len(results) >= 1
    assert any(r.path == "notes/first.md" for r in results)


def test_sync_skips_unchanged_files(tmp_path: Path, corpus: Path) -> None:
    db = SearchDB(tmp_path / "index.db")
    sync(db, corpus)
    stats = sync(db, corpus)
    assert stats.updated == 0
    assert stats.skipped == 2


def test_sync_prunes_deleted_files(tmp_path: Path, corpus: Path) -> None:
    db = SearchDB(tmp_path / "index.db")
    sync(db, corpus)
    (corpus / "notes" / "first.md").unlink()
    stats = sync(db, corpus)
    assert stats.deleted == 1
    assert all(r.path != "notes/first.md" for r in db.list_documents())


def test_sync_picks_up_modified_files(tmp_path: Path, corpus: Path) -> None:
    db = SearchDB(tmp_path / "index.db")
    sync(db, corpus)
    target = corpus / "notes" / "first.md"
    # Bump mtime well past the first sync to defeat fs resolution rounding.
    new_mtime = target.stat().st_mtime + 10
    target.write_text(target.read_text(encoding="utf-8") + "\n\nadded later", encoding="utf-8")
    import os
    os.utime(target, (new_mtime, new_mtime))
    stats = sync(db, corpus)
    assert stats.updated == 1


def test_rebuild_wipes_then_resyncs(tmp_path: Path, corpus: Path) -> None:
    db = SearchDB(tmp_path / "index.db")
    sync(db, corpus)
    stats = rebuild(db, corpus)
    assert stats.total == 2
    assert stats.updated == 2
    assert stats.skipped == 0


def test_sync_raises_on_missing_corpus(tmp_path: Path) -> None:
    db = SearchDB(tmp_path / "index.db")
    with pytest.raises(FileNotFoundError):
        sync(db, tmp_path / "does-not-exist")
