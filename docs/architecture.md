# Architecture

How `mcp-fts5-starter` is built, why each piece looks the way it does, and what didn't survive the extraction from the upstream project.

## The thesis

> For a small-to-medium personal corpus served from a single machine, BM25 over a SQLite FTS5 index — wired into Claude through MCP — beats the standard "vector DB + embedding API" stack on every axis except recall on heavily paraphrased queries. And recall on paraphrased queries is exactly the failure mode you can patch later by plugging an embedder into the existing index.

Everything below justifies that thesis or follows from it.

## Design pillars

### 1. FTS5-first, embeddings opt-in

The starter ships with no embedding provider. SQLite's built-in FTS5 module does BM25 ranking against tokenized text — fast, deterministic, zero network calls, and the index file is part of the same SQLite database your app probably already has.

The cost of being embedding-first instead would be:

- An embedding model in the dependency tree (local: slow + GPU-hungry; hosted: cost + rate limits + network coupling).
- A vector store, usually a separate service to monitor and back up.
- A re-embedding workflow when you change models, since vectors from one model can't be compared to queries from another.

That's a lot of moving parts to maintain a 24/7 retrieval service whose recall over a few thousand markdown files isn't even reliably better than well-tuned BM25.

The escape hatch is the [Embedder Protocol](../src/mcp_fts5_starter/embedding.py): when BM25 stops being enough, implement one method (`embed(texts) -> list[list[float]]`) and pass an instance to `SearchDB`. The schema already has a `notes_vec` table; the ranker already does Reciprocal Rank Fusion. No surgery required.

### 2. Generic schema, generic tools

The upstream project (`brain-knowledge-base`) had ~14 MCP tools, each tied to specific Obsidian folders and frontmatter conventions: `save_clipping`, `list_concepts`, `get_backlinks`, `save_session_summary`, and so on. Useful for that vault, useless for anyone else's.

The starter exposes four tools that work for any markdown corpus:

| Tool | Purpose |
|------|---------|
| `search` | BM25 (+ optional vector RRF) over the corpus |
| `list` | Page through indexed documents, optionally filtered by `doc_type` |
| `read` | Return a single document's raw content |
| `index` | Re-sync the corpus directory into the FTS5 index |

`doc_type` is the one concession to faceting. By default it's the parent directory name of each file (`concepts/foo.md` → `doc_type="concepts"`), so a corpus organized into folders gets a built-in filter without anyone declaring a schema. If you want a different convention, plug a custom `Extractor` and write whatever you want into `doc_type`.

### 3. Tokenizer is a knob

The default is FTS5's built-in `unicode61`. It tokenizes on Unicode whitespace and punctuation, splits Han characters into single-character tokens, and works fine for Latin-script content with occasional CJK sprinkles.

For CJK-heavy corpora, the `[jieba]` extra installs `jieba` and lets you opt into pre-segmentation. This isn't bundled by default because:

- It's an optional dependency users on English/Latin corpora shouldn't have to pull.
- The decision is corpus-specific, not language-specific — even within Chinese content, `jieba` only helps if your queries are multi-character phrases, not single characters or short tokens.
- It's a single environment variable to flip on (`MCP_FTS5_TOKENIZER=jieba`), so the cost of opting in is one-time.

This is a deliberate inversion of the "be helpful by default" instinct: starters that bundle every plausible tokenizer rot fast as their dependency tree drifts.

### 4. Incremental sync, no daemon

`SearchDB` keeps a `notes_meta` table mapping each indexed path to its last-seen `mtime`. Each `sync` pass walks the corpus, stats every file, and re-indexes only what's changed. For an edit-one-file workflow this means roughly one `INSERT OR REPLACE` per pass — cheap enough to run on every MCP `index` tool invocation, no file-watcher required.

A full rebuild (`SearchDB.rebuild` / `mcp-fts5-starter rebuild`) is the right call after schema, tokenizer, or embedder changes — anywhere stored tokens or vectors are no longer comparable to freshly-produced ones.

### 5. Separation of concerns: index vs. server vs. CLI

```
data/sample/         (corpus on disk — markdown files)
       │
       ▼
   ingest.sync   ←─ sync(db, corpus)
       │             • walks files
       │             • parses frontmatter
       │             • calls db.upsert(...)
       ▼
  SearchDB         ←─ FTS5 + optional vec
       │             db.search(query) → list[SearchResult]
       │             db.list_documents() → list[SearchResult]
       ▼
   server.py       ←─ FastMCP wraps the same SearchDB API
   cli.py          ←─ argparse wraps the same SearchDB API
```

The server and CLI are thin. All logic lives in `search.py` and `ingest.py`, which know nothing about MCP and have zero MCP imports. That means:

- Tests for ranking, RRF, frontmatter parsing, and incremental sync run without spinning up an MCP transport.
- You can use the index from a script, a Jupyter notebook, or another web framework without changing anything.
- Future transports (HTTP+SSE, a different agent framework) are a thin wrapper around the same API, not a fork.

This is the same shape as `smart-restart`'s decider/executor split: a pure core, with adapters at the edges.

## What didn't survive extraction

The upstream project had several pieces that intentionally didn't make it into the starter:

- **Memory decay (`heat_score`, `level`, archive table).** That's its own concern; see [forget-rag](https://github.com/zx22413/forget-rag), which is a sibling project also built on FTS5 but for a different problem.
- **URL deduplication (`notes_urls`).** Specific to a clipping ingestion workflow; not generic enough.
- **Concept-mention tracking + tag-affinity scoring.** Personalization features tied to the upstream's specific knowledge-graph workflow.
- **Domain-specific tools** (`save_clipping`, `save_session_summary`, `send_telegram`, `list_learning_notes`, `get_note_conversations`, etc.). Replaced by the four generic tools.
- **The wikilink-injection step** that called `claude -p` on every saved session. A nice trick, but it's a feature for the upstream vault, not the index.

The result is roughly 3x smaller (~700 lines of source vs. ~1700 in the upstream) and trivial to read end-to-end — which is the whole point of a starter.

## Comparison: when each option wins

| Dimension | mcp-fts5-starter (BM25) | + Embedder (hybrid) | Hosted vector DB |
|-----------|-------------------------|---------------------|------------------|
| Setup time | `pip install` + 1 env var | Same + provider keys | Account + cluster + SDK |
| Cold start | <100 ms | <100 ms | Seconds |
| Memory | <50 MB | + embedding model | Service-resident |
| Recall on exact terms | Excellent | Excellent | Variable (depends on chunking) |
| Recall on paraphrases | Weak | Strong | Strong |
| Cost per 10k docs | $0 | Embedding API calls only | Monthly subscription |
| Runs on a Pi | Yes | Yes (small embedder) | No |
| Vendor lock-in | None | Whatever provider you wire | Yes |

Numbers are intentionally absent from this table. Recall and latency depend so heavily on corpus and query shape that any single number would mislead at least as often as it helped. See [`benchmark.md`](benchmark.md) for a reproducible synthetic-corpus benchmark with index time, query latency, and memory at 100 / 1,000 / 10,000 docs.

## When to outgrow the starter

You're hitting the wall when:

- The corpus is hundreds of thousands of documents and BM25 differentiation is degrading.
- Queries reliably phrase concepts in words that don't appear in source documents.
- You need multi-tenant isolation (separate indexes per user, with hot upgrades).
- You need write-heavy concurrent indexing from many processes (SQLite handles concurrent reads fine, concurrent writers less so).

At that point: graduate. Meilisearch, Qdrant, OpenSearch, or a managed equivalent will earn their keep. The starter exists for everyone who *isn't* there yet — which, for personal knowledge bases, side projects, and most internal tools, is almost everyone.
