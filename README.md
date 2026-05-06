# mcp-fts5-starter

> Drop-in MCP server template with SQLite FTS5 search backend. ~300 lines, no vector DB, no embedding API, runs on a Pi.

[![PyPI](https://img.shields.io/pypi/v/mcp-fts5-starter?color=blue)](https://pypi.org/project/mcp-fts5-starter/)
[![test](https://github.com/zx22413/mcp-fts5-starter/actions/workflows/test.yml/badge.svg)](https://github.com/zx22413/mcp-fts5-starter/actions/workflows/test.yml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue)](pyproject.toml)

## The problem

You want to expose a corpus of notes, docs, or clippings to Claude (or any MCP client) as a search tool. Most tutorials reach for a vector DB, an embedding API, and a 500MB Docker image to retrieve a few thousand markdown files. For a small-to-medium corpus running on a single machine, that's overkill.

`mcp-fts5-starter` is the boring, dependable option:

- **SQLite FTS5** for full-text search — built into Python's `sqlite3`, no service to run
- **MCP server** scaffold with a few example tools (`search`, `list`, `read`)
- **One-file ingest script** that walks a directory of markdown files, parses frontmatter, and indexes them
- **No embeddings, no vectors, no GPU** — and no API bill

Drop the template into a new repo, point it at a folder, and you have a working MCP server in under 10 minutes.

## When to use this (and when not to)

**Use this if** your corpus is:

- Small-to-medium (up to ~100k documents)
- Mostly text (markdown, code, prose) where keyword + tag matching is enough
- Running on a single machine, Pi, or laptop
- Something you want to set up once and forget

**Don't use this if** you need:

- True semantic search across rephrased queries — pair this with embeddings, or use a different tool
- Multi-tenant search across millions of docs — use a real search backend (Elastic, Meilisearch, Qdrant)
- Memory decay / TTL on entries — see [forget-rag](https://github.com/zx22413/forget-rag) (which also uses FTS5 but for a different purpose)

### Sibling projects

| Repo | Angle |
|------|-------|
| `mcp-fts5-starter` (this) | MCP server **deployment template** — how to wire FTS5 + MCP together |
| [`forget-rag`](https://github.com/zx22413/forget-rag) | RAG library with **memory decay** — three-tier forgetting on top of FTS5 |

Both use SQLite FTS5 under the hood, but solve different problems. Need a starter? Here. Need decay logic? Forget-rag.

## Quick demo

The repo ships with a small synthetic corpus under `data/sample/` and a
one-shot script that builds an index and runs a few representative
queries against it:

```
git clone https://github.com/zx22413/mcp-fts5-starter
cd mcp-fts5-starter
uv sync                          # or: pip install -e .
python scripts/build-sample.py
```

Sample output:

```
Rebuilding index at data/sample/index.db
  indexed 7 doc(s): 7 written, 0 failed

Query: 'BM25 weights'
  - BM25 ranking                concepts/bm25.md
  - Why not just use a vector   notes/why-not-vector-db.md

Query: 'hybrid search'
  - Reciprocal rank fusion      concepts/rrf.md
  - Why not just use a vector   notes/why-not-vector-db.md

Query: 'tokenizer' [doc_type=notes]
  - Tokenization trade-offs     notes/tokenization-tradeoffs.md
  - Why not just use a vector   notes/why-not-vector-db.md
  - Incremental indexing        notes/incremental-indexing.md
```

To launch the MCP server against the same corpus (e.g. for use from
Claude Code), point at the directory and the index file:

```
MCP_FTS5_CORPUS=data/sample MCP_FTS5_DB=data/sample/index.db \
  mcp-fts5-starter serve
```

For a hosted deployment, swap stdio for `sse` or `streamable-http`:

```
mcp-fts5-starter serve --transport sse --host 0.0.0.0 --port 8765
```

## Architecture & benchmarks

- [`docs/architecture.md`](docs/architecture.md) — design pillars (FTS5-first, embeddings opt-in, generic schema/tools, incremental sync), what didn't survive extraction from the upstream project, and a comparison table for when BM25 / hybrid / hosted vector DB each makes sense.
- [`docs/benchmark.md`](docs/benchmark.md) — reproducible benchmark at 100 / 1,000 / 10,000 docs, plus the perf bug it surfaced.

## Examples

- [`examples/claude-code/`](examples/claude-code/) — drop-in `.mcp.json` for Claude Code, plus how-to and troubleshooting. Same shape works for Claude Desktop.
- [`examples/raw-jsonrpc/`](examples/raw-jsonrpc/) — talk to the server using bare JSON-RPC over stdio (no MCP SDK). Useful when writing a custom client or debugging a transport-level issue.

## Status

✅ **v0.1.0 shipped** ([PyPI](https://pypi.org/project/mcp-fts5-starter/) · [GitHub Release](https://github.com/zx22413/mcp-fts5-starter/releases/tag/v0.1.0) · [launch post](docs/blog/launch.md)).

## Roadmap to v0.1

- [x] 1. Initial scaffold
- [x] 2. Generic MCP tool layer (`search`, `list`, `read`, `index`)
- [x] 3. Generic FTS5 schema with BM25 tuning notes
- [x] 4. Sample corpus + one-command demo (`scripts/build-sample.py`)
- [x] 5. Architecture doc — [`docs/architecture.md`](docs/architecture.md)
- [x] 6. [`examples/`](examples/) — Claude Code config + raw JSON-RPC over stdio
- [x] 7. CI workflows (test on push/PR × py3.11/3.12/3.13; publish on release via OIDC)
- [x] 8. v0.1.0 release ([PyPI](https://pypi.org/project/mcp-fts5-starter/0.1.0/)) + [launch post](docs/blog/launch.md)

## License

MIT — see [LICENSE](LICENSE).
