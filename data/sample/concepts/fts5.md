---
title: SQLite FTS5
created: 2026-04-01
tags:
  - sqlite
  - search
  - fundamentals
---

## Summary

FTS5 is SQLite's built-in full-text search module. It indexes text columns
in a virtual table and answers `MATCH` queries with BM25-ranked results,
all without an external service or daemon.

## Why use it

Most "small to medium" search workloads — under a few hundred thousand
documents on a single host — don't benefit from a dedicated search backend.
FTS5 ships with the SQLite library that's already on every modern OS, so
the deployment story is "pip install your app, that's it."

## Building blocks

A typical FTS5 setup has three parts:

- A virtual `*_fts` table holding the tokenized text.
- A regular companion table holding original (untokenized) values for
  display, since the FTS5 columns are mangled by the chosen tokenizer.
- A small `_meta` table tracking file mtimes for incremental sync.

## Trade-offs

FTS5 does keyword matching with token overlap. It does not understand
synonyms, paraphrasing, or query intent. For semantic generalization you
need to layer dense vectors on top — see [[reciprocal rank fusion]] for the
standard fusion technique.
