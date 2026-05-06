---
title: Why not just use a vector database
created: 2026-04-09
tags:
  - hybrid-search
  - architecture
---

## Summary

Vector databases get top billing in most "build a RAG" tutorials, but for
a small-to-medium personal corpus they're often the wrong default. The
starter ships with BM25 only on purpose.

## The cost the tutorials skip

A vector-only stack pulls in:

- An embedding model — local (slow, GPU-hungry) or hosted (cost, rate
  limits, network dependency, vendor lock-in).
- A vector store — usually a separate service to run, monitor, back up,
  and upgrade.
- Re-embedding workflows when you change models, since stored vectors
  from one model are useless against queries embedded by another.

For a corpus of a few thousand markdown files, that's a lot of moving
parts to maintain a 24/7 retrieval service whose recall isn't even
clearly better than well-tuned BM25.

## When semantic search actually pays off

The break-even point arrives when:

- Queries phrase concepts in ways that don't share keywords with the
  source documents (paraphrasing, abbreviations, translations).
- The corpus is large enough (tens to hundreds of thousands of docs)
  that BM25's ability to differentiate degrades.
- You have a clear evaluation set and can prove the lift.

Until then, a tuned BM25 — with sensible per-column weights, a working
tokenizer for the language, and frontmatter-aware ingest — covers most
real workloads without the operational tax.

## The escape hatch

The starter still wires in an `Embedder` Protocol so you can graduate to
hybrid retrieval the day BM25 stops being enough. See the embedding
example for how to plug a real provider in. Until then: don't pay for
what you don't need.
