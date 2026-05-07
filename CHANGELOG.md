# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-05-08

### Added

- HTTP transports for hosted deployments. `mcp-fts5-starter serve --transport sse|streamable-http [--host H] [--port P]` binds a TCP listener instead of stdio. stdio remains the default for local clients (Claude Code, Claude Desktop). Built on FastMCP's native transport support — no new dependencies.
- `docs/benchmark.md` — reproducible synthetic-corpus benchmark at 100 / 1k / 10k docs with index time, query latency p50/p95/p99, DB size, and peak Python heap. `scripts/benchmark.py` is the runner.

### Changed

- **Ingest is ~2× faster.** `SearchDB.upsert` and `delete` gained a `commit` keyword (default `True`); `ingest.sync` and `rebuild` now batch a single commit at the end of the loop instead of fsync-per-document. Surfaced by the new benchmark — was the largest measured cost on Windows NTFS.
- `schema.connect` enables `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`. Modern SQLite defaults for read-heavy applications; the right trade-off for a search index that can always be rebuilt from disk.

## [0.1.0] - 2026-05-07

Initial public release. A drop-in MCP server template with a SQLite FTS5 search backend — extracted, generalized, and stripped down from a closed-source personal knowledge base that's been running this pattern for ~18 months.

### Added

#### Core indexer

- `SearchDB` — FTS5 + optional vector RRF fusion, with explicit BM25 per-column weighting (`title=10`, `tags=8`, `summary=5`, `content=1` by default).
- Incremental sync by file `mtime` — re-indexes only what's changed, prunes deletions, no daemon required.
- `Extractor` Protocol so non-markdown corpora can be ingested by plugging a custom function.
- Default markdown extractor: parses YAML frontmatter (title/tags/created), pulls a Summary heading or first paragraph, merges body `[[wikilink]]` tokens into tags, derives `doc_type` from the parent folder name.
- `Embedder` Protocol — bring-your-own embedding provider; the schema reserves a `notes_vec` table that stays empty until you wire one in.
- Reciprocal Rank Fusion (RRF, `k=60`) merges BM25 + vector results when an embedder is configured.
- Defensive vector dimension check: stored vectors with a different dim than the current query embedder are skipped with a warning instead of silently truncating via `zip()`. (Preserved from a real upstream bug — see the launch blog post.)
- Tokenizer is a knob. Default: SQLite's built-in `unicode61`. Optional: `jieba` Chinese segmentation via `pip install mcp-fts5-starter[jieba]` and `MCP_FTS5_TOKENIZER=jieba`.
- `LIKE` fallback when an FTS5 `MATCH` query is malformed (e.g. unbalanced quote) so the tool stays usable on bad input.

#### MCP server (4 tools)

- `search(query, limit, doc_type)` — BM25 retrieval (+ vector RRF if embedder is configured).
- `list(doc_type, limit, offset)` — page through indexed documents.
- `read(path)` — fetch a single document's raw content.
- `index()` — re-sync the corpus directory into the FTS5 index.
- Built on `FastMCP` (the official `mcp` Python SDK), stdio transport.
- Env-var configuration: `MCP_FTS5_CORPUS`, `MCP_FTS5_DB`, `MCP_FTS5_TOKENIZER`.

#### CLI

- `mcp-fts5-starter serve` — run the MCP server.
- `mcp-fts5-starter index` — incremental sync of a corpus directory.
- `mcp-fts5-starter rebuild` — wipe the index and reindex everything.
- `mcp-fts5-starter search <query>` — one-off query against the index.
- `mcp-fts5-starter list` — page through indexed documents.

#### Sample corpus

- 7 synthetic markdown notes under `data/sample/{concepts,notes}/` covering FTS5, BM25, RRF, MCP, tokenization trade-offs, why-not-vectors, and incremental indexing — chosen to double as documentation.
- `scripts/build-sample.py` — one-command rebuild + three representative searches against the sample, end-to-end.

#### Examples

- `examples/claude-code/` — drop-in `.mcp.json` config with a verify-it-works walkthrough and troubleshooting notes. Same shape works for Claude Desktop.
- `examples/raw-jsonrpc/demo.py` — a longhand JSON-RPC client that spawns the server, runs the initialize handshake, lists tools, and calls `search`. Logs every wire message so the protocol is legible. Useful when writing a custom client or debugging a transport issue.

#### Documentation

- README — quick demo, when-to-use vs when-not-to, sibling-repo positioning vs [`forget-rag`](https://github.com/zx22413/forget-rag).
- `docs/architecture.md` — five design pillars (FTS5-first, generic schema/tools, tokenizer-as-knob, incremental sync, index/server/CLI separation), what didn't survive extraction from the upstream project, and a qualitative comparison table for BM25 / hybrid / hosted vector DB.
- `docs/blog/launch.md` — launch post: why this template exists and one specific bug preserved as a defensive log.

#### Project infrastructure

- 28 hermetic unit tests (frontmatter parsing, tokenizer resolution, BM25 search, doc-type filtering, path-prefix scoping, LIKE fallback, RRF fusion with a fake embedder, incremental sync, prune-on-delete, modify detection, rebuild).
- GitHub Actions CI: ruff lint + pytest on Python 3.11 / 3.12 / 3.13 (Ubuntu).
- Publish workflow: GitHub Release → `uv build` → PyPI via OIDC trusted publishing (no API token).

### Notes

- **No embedding provider bundled.** The `Embedder` Protocol is one method (`embed(texts) -> list[list[float]]`); see `src/mcp_fts5_starter/embedding.py` for the contract. Wiring Gemini, OpenAI, sentence-transformers, or Ollama is roughly a 30-line adapter.
- **Memory decay is out of scope.** The upstream project had a three-tier forgetting system; that lives in [`forget-rag`](https://github.com/zx22413/forget-rag) instead. The two repos cross-link in their READMEs.
- **HTTP+SSE transport deferred.** stdio works for local Claude Code / Claude Desktop integrations and that's the dominant use case. SSE can be added without changing the index layer.
- **No real benchmark numbers in the architecture doc** — fabricated benchmarks mislead more than help. Real numbers will land alongside a reproducible fixture in a future minor.

[Unreleased]: https://github.com/zx22413/mcp-fts5-starter/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/zx22413/mcp-fts5-starter/releases/tag/v0.2.0
[0.1.0]: https://github.com/zx22413/mcp-fts5-starter/releases/tag/v0.1.0
