---
title: Tokenization trade-offs
created: 2026-04-08
tags:
  - tokenization
  - cjk
---

## Summary

The choice of tokenizer determines what counts as a "term" in the index.
For Latin scripts the defaults are nearly always fine. For CJK content
(Chinese, Japanese, Korean) the choice shapes recall on multi-character
queries.

## The default: unicode61

FTS5's built-in `unicode61` tokenizer splits on Unicode whitespace and
punctuation. Latin words become Latin tokens. Han characters become
single-character tokens — every character is its own term.

This works for short Chinese queries against short Chinese fields (titles,
tags) but degrades for long queries: a phrase like "代理工具設計" gets
split into four separate tokens, and FTS5's default `MATCH` semantics
require all of them but in any order, which dilutes ranking.

## The alternative: jieba pre-segmentation

`jieba` is a popular Chinese segmenter. Running text through `jieba` *before*
inserting into FTS5 produces multi-character tokens that better reflect
how Chinese readers actually parse a phrase.

The starter exposes this as an opt-in extra:

    pip install mcp-fts5-starter[jieba]

Then either pass `tokenizer="jieba"` to `SearchDB` or set
`MCP_FTS5_TOKENIZER=jieba` in the environment.

## When it's worth the dependency

Roughly: if more than 30% of your corpus is CJK and most queries are
multi-character phrases, jieba materially lifts recall. If you're
indexing English documentation and a few Chinese sprinkles, unicode61
is fine.
