# A boring middle-ground search backend for Claude

> English | [繁體中文](launch.zh-TW.md)


Most "build a RAG over your notes" tutorials I've read in the last year reach for the same stack: an embedding model, a vector database, and 500MB of Docker images. For a personal corpus of a few thousand markdown files served to one user from one machine, that's overkill — and the operational cost lives forever after the tutorial is over.

I just released [`mcp-fts5-starter`](https://github.com/zx22413/mcp-fts5-starter) v0.1.0 — a drop-in MCP server template that uses SQLite FTS5 for full-text search instead. Three hundred lines of source, no separate service, runs on a Pi. Claude Code talks to it the moment you `pip install`.

This post is about why FTS5 keeps deserving a default seat that nobody seems to give it, what the upstream project I extracted this from did to earn its 18-month track record, and one specific bug I shipped two embeddings ago that's now preserved as a defensive log in the new repo.

## The thesis: FTS5 is enough until it isn't

Three things are true at the same time:

- **Vector search is genuinely useful.** Paraphrased queries, abbreviations, translations — keyword matching can't bridge any of them.
- **Vector search is the wrong default for most personal corpora.** A few thousand markdown files don't need 24/7 semantic retrieval. They need keyword search that runs in milliseconds with no moving parts.
- **The interface between the two is well understood.** Reciprocal Rank Fusion is one paragraph of code that fuses BM25 ranks with vector cosine similarity ranks. You can graduate from "BM25 only" to "hybrid retrieval" without changing the data model.

The starter takes those three facts seriously. It ships with FTS5 only — no embeddings, no provider keys, no tokens-per-query budget. The schema reserves a `notes_vec` table that stays empty until you wire an embedder in. The ranker already does RRF fusion; it just has nothing to fuse until you give it something. The day BM25 stops being enough — and for many corpora, that day never comes — graduating is a 30-line adapter file, not a migration.

This is the same shape as putting an interface in front of your DB driver years before you swap databases. The cost is near-zero now, the option value is large later, and you don't pay for what you don't need today.

## What I cut when extracting

The starter is a stripped-down version of `brain-knowledge-base`, the closed-source MCP server I've been running against my Obsidian vault for the last 18 months. Three things had to come out.

**1. Memory decay.** The upstream project has a three-tier forgetting system (`heat_score`, `level`, archive table) — older notes that no one searches for migrate to a colder index. That's its own problem domain, and it now lives in [`forget-rag`](https://github.com/zx22413/forget-rag), a sibling repo I shipped yesterday. The two cross-link in their READMEs: need decay? Go there. Need a starter? Stay here.

**2. Domain tools.** The upstream had ~14 MCP tools tied to the vault layout: `save_clipping`, `list_concepts`, `get_backlinks`, `save_session_summary`, `send_telegram`. Useful for that vault, useless for anyone else's. Replaced by four generic tools: `search`, `list`, `read`, `index`. The `doc_type` parameter — derived by default from each file's parent folder name — gives anyone a built-in faceted filter without forcing them to declare a schema.

**3. Personalization.** Concept-mention tracking, tag-affinity scoring, an LLM-driven wikilink-injection step that called `claude -p` on every saved session. All clever, all coupled to my workflow. None of it belongs in a starter.

The result is roughly 3× smaller (~700 lines vs. ~1700 in the upstream) and trivial to read end-to-end — which is the whole point.

## The bug that paid for the dimension check

The defensive code I'm proudest of in the starter is six lines:

```python
if len(vec) != query_dim:
    logger.warning(
        "vec dim mismatch (stored=%d, query=%d) at path=%s — re-index needed",
        len(vec),
        query_dim,
        row[0],
    )
    continue
```

It exists because of a real bug I shipped to myself a couple of months ago.

The upstream project originally used a local Ollama instance with `bge-m3` for embeddings. 1024-dimensional vectors. Everything worked, search felt great, life was good. Then Gemini's `gemini-embedding-001` got cheap enough that I decided to migrate — better recall on Chinese phrasing, no Ollama daemon to babysit. 1536-dimensional vectors. I flipped `EMBEDDING_PROVIDER=gemini`, restarted, ran some test queries, and got back results that felt vaguely off but not obviously wrong. I shrugged and moved on.

A few weeks later I noticed search was returning unrelated notes for queries that used to nail the right ones. Spent half an evening grepping through ranking code looking for a stale hyperparameter. The actual bug: cosine similarity was being computed via `zip(query_vec, stored_vec)`, which silently truncates to the shorter list. Brand-new 1536-D query vectors were being compared against the first 1024 dimensions of stored 1024-D vectors. The math still produced a number. The number was meaningless. Search degraded gracefully into garbage.

The fix in the upstream project was a one-time migration script (`migrate_embeddings_to_gemini.py`) that re-embedded everything with the new model. The fix in the starter is the dim check above — if a stored vector has a different dim than the current query embedder, skip it loudly. The architecture doc has a corresponding line: **"After changing the embedder, run `rebuild`. Anywhere stored tokens or vectors are no longer comparable to freshly-produced ones, the only safe move is full reindex."**

The lesson I keep relearning: silent type-coercion is worse than crashes. `zip()` truncating short was the technically correct Python semantic and the wrong tool for the job. `zip(strict=True)` would have raised on the first comparison and saved me three weeks of subtly bad search results.

## How to try it

```bash
git clone https://github.com/zx22413/mcp-fts5-starter
cd mcp-fts5-starter
uv sync
python scripts/build-sample.py
```

The build script indexes seven synthetic markdown notes that double as documentation (FTS5, BM25, RRF, MCP, tokenization, why-not-vectors, incremental indexing) and runs three representative searches end-to-end. About ten seconds, top to bottom.

Wire it into Claude Code with the `.mcp.json` snippet in [`examples/claude-code/`](../../examples/claude-code/) and the model gets four tools — `search`, `list`, `read`, `index` — against any directory of markdown files you point at it. Or skip the SDK and talk to the server in raw JSON-RPC over stdio with [`examples/raw-jsonrpc/demo.py`](../../examples/raw-jsonrpc/demo.py), which logs every wire message so the protocol stops being a black box.

If your corpus is mostly Chinese, `pip install mcp-fts5-starter[jieba]` and set `MCP_FTS5_TOKENIZER=jieba` to opt into pre-segmentation. If you outgrow BM25, implement the one-method `Embedder` Protocol and pass it to `SearchDB` — the schema and ranker were waiting for you the whole time.

## What's next

The starter is intentionally not a product roadmap. It's a v0.1.0 release that's deliberately small enough to read in one sitting, with the option value baked in for the parts you might need later. The next minors will land:

- A real benchmark fixture in `docs/benchmark.md` with reproducible numbers (no fabricated comparisons in the architecture doc — see the comparison table for the qualitative version).
- An `Embedder` example wired to a real provider, as a separate small repo so the core stays dependency-light.
- HTTP+SSE transport for hosted deployments.

Until then: pip install, point it at a folder, and stop paying for what you don't need.

---

[`mcp-fts5-starter` on GitHub](https://github.com/zx22413/mcp-fts5-starter) · [PyPI](https://pypi.org/project/mcp-fts5-starter/) · [architecture doc](../architecture.md) · [`forget-rag`](https://github.com/zx22413/forget-rag) (sibling repo for memory-decay)
