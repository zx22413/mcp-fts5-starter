# Raw JSON-RPC over stdio

Talk to the MCP server the same way Claude Code does — JSON-RPC 2.0 messages, one per line, over the server subprocess's stdin/stdout — but written out longhand so you can see every byte.

This is the level of detail you'd need if you were:

- Writing your own MCP client.
- Embedding the starter in a non-MCP framework that just speaks JSON-RPC.
- Debugging a "why isn't Claude Code calling my tool?" issue.

If you just want to use the server from Claude Code, see [`../claude-code/`](../claude-code/) — that's the easy path.

## Run it

```
python scripts/build-sample.py        # build the sample index first
python examples/raw-jsonrpc/demo.py
```

The script does four things:

1. Spawns `mcp-fts5-starter serve` as a subprocess with the sample corpus env vars.
2. Sends an `initialize` request and reads the server's capabilities.
3. Sends `tools/list` and prints each advertised tool.
4. Sends `tools/call` for `search("BM25 weights")` and prints the returned content.

Every send and receive is logged in `>>` / `<<` form so you can see the wire protocol.

## What you'll see

Roughly:

```
>> {"jsonrpc": "2.0", "method": "initialize", "params": {"protocolVersion": "2024-11-05", ...}, "id": 1}
<< {"jsonrpc":"2.0","id":1,"result":{"protocolVersion":"2024-11-05","capabilities":{...},"serverInfo":{...}}}

>> {"jsonrpc": "2.0", "method": "notifications/initialized"}

>> {"jsonrpc": "2.0", "method": "tools/list", "id": 2}
<< {"jsonrpc":"2.0","id":2,"result":{"tools":[{"name":"search",...}, ...]}}

-- server advertises 4 tool(s) --
  - search: Search the indexed corpus.
  - list: List indexed documents.
  - read: Read the raw content of a single indexed document.
  - index: Re-sync the corpus directory into the FTS5 index. ...

-- calling search('BM25 weights') --
>> {"jsonrpc": "2.0", "method": "tools/call", "params": {"name":"search","arguments":{"query":"BM25 weights","limit":3}}, "id": 3}
<< {"jsonrpc":"2.0","id":3,"result":{"content":[{"type":"text","text":"Found 2 result(s):\n\n**BM25 ranking** ..."}], ...}}
```

## Protocol notes

- **Newline-delimited JSON.** One message per line over stdio. Don't pretty-print.
- **Initialize handshake is mandatory.** The spec requires a `notifications/initialized` after the `initialize` response before any other request. Skip it and the server may refuse subsequent calls.
- **Notifications have no `id`.** Notifications (e.g. `notifications/initialized`) get no response. Requests have an `id`; the server echoes it in the response.
- **Errors have a different shape.** Successful responses carry a `result`; failed ones carry an `error: {code, message, data?}`. The demo doesn't show this path — touch the protocol incorrectly and the server replies with an error object you can inspect.
