---
title: Reciprocal rank fusion
created: 2026-04-03
tags:
  - hybrid-search
  - ranking
---

## Summary

Reciprocal rank fusion (RRF) is a simple, parameter-light way to combine
results from multiple ranked retrievers. It uses each document's *rank*
in each list, not the underlying scores — which means you can fuse
[[bm25 ranking]] output with dense-vector cosine similarity without
worrying about score calibration.

## Formula

For document `d` and a set of retrievers `R`:

    rrf_score(d) = sum over r in R of  1 / (k + rank_r(d))

`k` is a constant; the original paper uses 60 and the starter inherits
that default. Documents missing from a retriever simply contribute 0
from that retriever.

## Why ranks instead of scores

Different retrievers output scores on incompatible scales:

- BM25 emits unbounded negative numbers.
- Cosine similarity on L2-normalized vectors lives in `[-1, 1]`.
- Some neural retrievers emit raw logits with no fixed range.

Trying to mix these directly requires a normalization step that itself
needs tuning. RRF sidesteps the problem by working only with ordering.

## When RRF helps

Hybrid search — keyword + semantic — is the textbook use case. BM25 nails
exact matches and rare terms; vector search nails paraphrases and
synonyms. RRF reliably picks up the union without tuning.
