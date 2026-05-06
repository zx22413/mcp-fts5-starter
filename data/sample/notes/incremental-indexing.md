---
title: Incremental indexing
created: 2026-04-10
tags:
  - ingest
  - operations
---

## Summary

Re-indexing the entire corpus on every change is fine for a hundred
files. It's intolerable for a hundred thousand. The starter's `sync` is
designed to be cheap to call repeatedly — the dominant cost is reading
the file system, not writing to FTS5.

## How it works

`SearchDB` keeps a `notes_meta` table mapping each indexed path to its
last-seen `mtime`. Each `sync` pass:

1. Walks the corpus directory and stats every file.
2. Compares each file's current mtime against `notes_meta`.
3. Re-indexes only the files where mtime has changed.
4. Drops paths that exist in the index but no longer on disk.

For a typical edit-one-file workflow, this means you do one `INSERT OR
REPLACE` and zero deletes per re-index — fast enough to wire into a
file-watcher if you want near-real-time freshness.

## Edge cases worth knowing about

- **Touch without content change**: the file's mtime advances even if
  the body is identical. The index will dutifully re-index it. Cheap
  enough not to bother fingerprinting unless your corpus is huge.
- **Clock skew**: if files are written from another machine with a
  slower clock, their mtime can be older than what's already in the
  index. They won't be picked up until something else bumps the mtime.
  Workaround: `mcp-fts5-starter rebuild`.
- **Renames**: a renamed file looks like a delete + insert. That's
  correct from the index's perspective.

## When a full rebuild is the right call

After changing the FTS5 schema, the tokenizer, or the embedder. The
existing tokens or stored vectors are no longer comparable with
freshly-produced ones, so the only safe move is `rebuild`.
