# mcp-fts5-starter

> Drop-in MCP server template with SQLite FTS5 search backend. ~300 lines, no vector DB, no embedding API, runs on a Pi.

[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)
[![Status](https://img.shields.io/badge/status-alpha-orange)](#status)
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

## Status

🚧 **Alpha — scaffold only.** Source porting and example tools are in progress. See [ROADMAP](#roadmap) below.

## Roadmap to v0.1

- [x] 1. Initial scaffold (this commit)
- [ ] 2. Generic MCP tool layer (`search`, `list`, `read`) — port from brain-knowledge-base, strip domain coupling
- [ ] 3. Generic FTS5 schema (content + metadata + tags) with BM25 tuning notes
- [ ] 4. `data/sample.db` one-command demo
- [ ] 5. Architecture doc — "Why MCP + FTS5 beats vector DB for small corpora"
- [ ] 6. `examples/` — Claude Code config + curl usage
- [ ] 7. Tests + CI
- [ ] 8. v0.1.0 release + blog post

## License

MIT — see [LICENSE](LICENSE).
