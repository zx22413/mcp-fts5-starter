"""Walk a directory of markdown files and feed them into the index.

Designed around incremental syncs: ingest reads each file's mtime and skips
whatever already matches what's stored in ``notes_meta``. A full rebuild is
just :meth:`SearchDB.upsert` after wiping the tables — see ``rebuild`` below.

The default extractor treats markdown frontmatter as the source of truth for
title/tags/created, with the body becoming the searchable content. If your
corpus uses a different layout, plug a custom :class:`Extractor`.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from . import frontmatter
from .search import SearchDB

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Document:
    """Normalized payload ready for ``SearchDB.upsert``."""

    path: str
    title: str
    summary: str
    content: str
    tags: str
    doc_type: str
    created: str
    mtime: float


Extractor = Callable[[Path, Path], Document]


def default_extractor(file: Path, root: Path) -> Document:
    """Read a markdown file and produce a :class:`Document`.

    Conventions:

    - ``path`` is the file's path relative to ``root``, POSIX-style.
    - ``title`` comes from frontmatter ``title`` or the file stem.
    - ``summary`` is either a ``## Summary`` / ``## 摘要`` section, or the
      first paragraph after the frontmatter (whichever is non-empty first).
    - ``tags`` are joined with spaces — frontmatter tags first, then any
      ``[[wikilink]]`` tokens found in the body.
    - ``doc_type`` defaults to the parent directory name. This gives a
      built-in faceted filter ("clippings" vs "concepts" vs "sessions")
      without forcing every corpus to declare a schema.
    """
    text = file.read_text(encoding="utf-8", errors="ignore")
    meta = frontmatter.parse(text)
    body = frontmatter.strip(text)

    rel = file.relative_to(root).as_posix()
    title = meta.title or file.stem
    summary = _extract_summary(body)
    tag_tokens = list(meta.tags) + _extract_wikilinks(body)
    tags = " ".join(dict.fromkeys(t for t in tag_tokens if t))  # de-dup, order preserved
    doc_type = file.parent.name if file.parent != root else ""
    return Document(
        path=rel,
        title=title,
        summary=summary,
        content=text,
        tags=tags,
        doc_type=doc_type,
        created=meta.created,
        mtime=file.stat().st_mtime,
    )


def sync(
    db: SearchDB,
    root: str | Path,
    *,
    glob: str = "**/*.md",
    extractor: Extractor = default_extractor,
) -> SyncStats:
    """Incrementally bring ``root`` into ``db``.

    Files unchanged since the last index pass (matched by mtime) are skipped.
    Files removed from disk get pruned from the index.
    """
    root_path = Path(root).resolve()
    if not root_path.exists():
        raise FileNotFoundError(f"corpus root does not exist: {root_path}")

    known = db.known_paths()
    seen: set[str] = set()
    updated = 0
    skipped = 0
    failed = 0

    for file in _iter_files(root_path, glob):
        try:
            doc = extractor(file, root_path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("extract failed for %s: %s", file, exc)
            failed += 1
            continue
        seen.add(doc.path)
        prior_mtime = known.get(doc.path)
        if prior_mtime is not None and prior_mtime == doc.mtime:
            skipped += 1
            continue
        db.upsert(
            path=doc.path,
            title=doc.title,
            summary=doc.summary,
            content=doc.content,
            tags=doc.tags,
            doc_type=doc.doc_type,
            created=doc.created,
            mtime=doc.mtime,
        )
        updated += 1

    deleted = 0
    for stale in set(known) - seen:
        db.delete(stale)
        deleted += 1

    stats = SyncStats(
        total=len(seen), updated=updated, skipped=skipped, deleted=deleted, failed=failed
    )
    logger.info(
        "sync complete: total=%d updated=%d skipped=%d deleted=%d failed=%d",
        stats.total,
        stats.updated,
        stats.skipped,
        stats.deleted,
        stats.failed,
    )
    return stats


def rebuild(
    db: SearchDB,
    root: str | Path,
    *,
    glob: str = "**/*.md",
    extractor: Extractor = default_extractor,
) -> SyncStats:
    """Wipe the index and reindex everything under ``root``."""
    for table in ("notes_fts", "notes_meta", "notes_display", "notes_vec"):
        db.conn.execute(f"DELETE FROM {table}")
    db.conn.commit()
    return sync(db, root, glob=glob, extractor=extractor)


@dataclass(frozen=True)
class SyncStats:
    total: int
    updated: int
    skipped: int
    deleted: int
    failed: int


def _iter_files(root: Path, glob: str) -> Iterable[Path]:
    for p in sorted(root.glob(glob)):
        if p.is_file():
            yield p


_SUMMARY_HEADING = re.compile(r"^##\s+(?:Summary|摘要)\s*$", re.MULTILINE)
_WIKILINK = re.compile(r"\[\[([^\[\]|]+?)\]\]")


def _extract_summary(body: str) -> str:
    """Pick a short summary from the body."""
    match = _SUMMARY_HEADING.search(body)
    if match:
        rest = body[match.end() :].lstrip("\n")
        # Take everything until the next heading or blank-line block.
        section = re.split(r"\n##\s", rest, maxsplit=1)[0].strip()
        if section:
            return section[:500]
    # Fallback: first non-empty paragraph.
    for chunk in body.split("\n\n"):
        chunk = chunk.strip()
        if chunk and not chunk.startswith("#"):
            return chunk[:500]
    return ""


def _extract_wikilinks(body: str) -> list[str]:
    return [m.strip() for m in _WIKILINK.findall(body) if m.strip()]
