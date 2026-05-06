"""Talk to the MCP server using raw JSON-RPC 2.0 over stdio.

This is what an MCP client like Claude Code does under the hood, just
written out longhand so you can see every byte. No MCP SDK, no client
library — just Python's ``subprocess`` plus ``json``.

Run from the repo root::

    python scripts/build-sample.py        # build the sample index first
    python examples/raw-jsonrpc/demo.py

Expected output: the four tools advertised by the server, plus the result
of calling ``search("BM25 weights")`` against the sample corpus.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SAMPLE_CORPUS = REPO_ROOT / "data" / "sample"
SAMPLE_DB = SAMPLE_CORPUS / "index.db"


def request(method: str, params: dict | None = None, *, request_id: int | None = None) -> dict:
    """Build a JSON-RPC 2.0 request envelope. Notifications omit ``id``."""
    msg: dict = {"jsonrpc": "2.0", "method": method}
    if params is not None:
        msg["params"] = params
    if request_id is not None:
        msg["id"] = request_id
    return msg


def send(proc: subprocess.Popen, msg: dict) -> None:
    """Write one JSON-RPC message to the server's stdin (newline-delimited)."""
    line = json.dumps(msg) + "\n"
    print(f">> {json.dumps(msg)}")
    assert proc.stdin is not None
    proc.stdin.write(line)
    proc.stdin.flush()


def recv(proc: subprocess.Popen) -> dict:
    """Read one JSON-RPC message from the server's stdout."""
    assert proc.stdout is not None
    line = proc.stdout.readline()
    if not line:
        raise RuntimeError("server closed stdout unexpectedly")
    msg = json.loads(line)
    print(f"<< {json.dumps(msg)}")
    return msg


def main() -> int:
    if not SAMPLE_DB.exists():
        print(
            f"Sample index not found at {SAMPLE_DB}.\n"
            f"Run: python scripts/build-sample.py",
            file=sys.stderr,
        )
        return 1

    env = os.environ.copy()
    env["MCP_FTS5_CORPUS"] = str(SAMPLE_CORPUS)
    env["MCP_FTS5_DB"] = str(SAMPLE_DB)

    # On Windows, use sys.executable -m to avoid PATH lookup issues; the
    # script entry point ``mcp-fts5-starter`` works too if it's on PATH.
    cmd = [sys.executable, "-m", "mcp_fts5_starter.cli", "serve"]
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        env=env,
        bufsize=1,
    )

    try:
        # 1. Initialize handshake. Client advertises protocol version and
        #    capabilities; server responds with what it supports.
        send(
            proc,
            request(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "raw-jsonrpc-demo", "version": "0.0.1"},
                },
                request_id=1,
            ),
        )
        recv(proc)

        # 2. Per the spec, the client must follow ``initialize`` with a
        #    ``notifications/initialized`` (no id, no response expected).
        send(proc, request("notifications/initialized"))

        # 3. Ask what tools the server exposes.
        send(proc, request("tools/list", request_id=2))
        tools_response = recv(proc)
        tools = tools_response.get("result", {}).get("tools", [])
        print(f"\n-- server advertises {len(tools)} tool(s) --")
        for t in tools:
            print(f"  - {t['name']}: {t.get('description', '').splitlines()[0]}")

        # 4. Call ``search`` with a representative query.
        print("\n-- calling search('BM25 weights') --")
        send(
            proc,
            request(
                "tools/call",
                {"name": "search", "arguments": {"query": "BM25 weights", "limit": 3}},
                request_id=3,
            ),
        )
        call_response = recv(proc)
        content = call_response.get("result", {}).get("content", [])
        for item in content:
            if item.get("type") == "text":
                print("\n-- result text --")
                print(item["text"])
    finally:
        if proc.stdin:
            proc.stdin.close()
        proc.wait(timeout=5)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
