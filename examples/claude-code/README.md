# Claude Code integration

Wire `mcp-fts5-starter` into Claude Code so the model can call the four tools (`search`, `list`, `read`, `index`) against your corpus.

## Prerequisites

```
pip install mcp-fts5-starter        # or: uv add mcp-fts5-starter
python scripts/build-sample.py      # builds the demo index this config points at
```

The starter must be importable as a script (`mcp-fts5-starter`) on the same `PATH` Claude Code launches subprocesses with. If `which mcp-fts5-starter` returns nothing in the shell you started Claude Code from, the MCP server won't launch — install it into the same environment.

## Configure

Copy [`.mcp.json`](./.mcp.json) into the root of any Claude Code project that should expose the index:

```
cp examples/claude-code/.mcp.json /path/to/your/project/.mcp.json
```

Edit `MCP_FTS5_CORPUS` to point at the directory of markdown files you want indexed, and `MCP_FTS5_DB` to wherever the index file should live. The example uses `${workspaceFolder}` which Claude Code expands to the project root.

Restart Claude Code (or reload the workspace). On startup it spawns the MCP server as a subprocess, calls `initialize`, and registers the advertised tools.

## Verify it's working

In Claude Code, open the `/mcp` panel (or whatever the current shortcut is — see Claude Code's docs). You should see `fts5-starter` listed with four tools:

- `search(query, limit, doc_type)`
- `list(doc_type, limit, offset)`
- `read(path)`
- `index()`

Then ask a question that requires the tool — for example:

> Search my notes for "BM25 weights"

Claude should call `search`, get back the ranked results from your corpus, and reason over them.

## Re-indexing

Two options:

1. Tell Claude to call `index`, e.g. "Re-sync the FTS5 index." It runs the same `ingest.sync` you'd run from the CLI, just without leaving the chat.
2. Run `mcp-fts5-starter index --corpus ... --db ...` in a terminal whenever you batch-update the corpus. Either works; the index file is the same.

## Claude Desktop

Claude Desktop uses `claude_desktop_config.json` (in the per-platform config dir) instead of project-scoped `.mcp.json`. The shape is the same — copy the `mcpServers` block from [`.mcp.json`](./.mcp.json) into the desktop config and you're done.

## Troubleshooting

- **"server failed to start"**: check that `mcp-fts5-starter` is on `PATH` (`which mcp-fts5-starter`). Reinstall in the environment Claude Code uses.
- **"no documents indexed"**: run `mcp-fts5-starter index` (or the demo script) once before launching Claude Code. The server doesn't auto-index on startup — that's a deliberate cost decision, see [architecture.md](../../docs/architecture.md).
- **Wrong corpus**: env vars in `.mcp.json` override anything in your shell. Edit them in the file, then restart Claude Code.
