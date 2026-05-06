---
title: Model Context Protocol
created: 2026-04-04
tags:
  - mcp
  - protocol
---

## Summary

The Model Context Protocol (MCP) is an open spec for connecting large
language model clients to external data sources and tools. An MCP server
advertises a set of tools, resources, and prompts; an MCP client (such as
Claude Code or Claude Desktop) lets the model call those tools when
relevant to a user's request.

## Why this matters for search

Search is the canonical "tool" use case. The model knows it should look
something up; the user wants results from *their* corpus, not the open
web; and the protocol cleanly separates the model's reasoning from the
deterministic retrieval logic.

This starter implements four such tools:

- `search` — BM25 retrieval over the indexed corpus.
- `list` — page through what's currently indexed.
- `read` — fetch a single document's raw content.
- `index` — re-sync the on-disk corpus into the FTS5 index.

## Transport

MCP defines two standard transports:

- **stdio** — the default for locally-launched servers. The client
  spawns the server as a subprocess and exchanges JSON-RPC over its
  pipes. The starter uses this transport.
- **HTTP+SSE** — for remotely hosted servers. Out of scope for a "runs
  on a Pi" template, but trivially added later if needed.
