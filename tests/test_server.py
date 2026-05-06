"""Server entry-point tests.

We don't spin up a real transport here — the stdio path is exercised by
the raw-jsonrpc demo, and SSE/streamable-http by the README smoke
instructions. This file just covers the validation and settings-mutation
that ``server.main`` does before delegating to FastMCP.
"""

from __future__ import annotations

import pytest

from mcp_fts5_starter import server


def test_main_rejects_unknown_transport() -> None:
    with pytest.raises(ValueError, match="unknown transport"):
        server.main(transport="websocket")  # type: ignore[arg-type]


def test_main_mutates_host_and_port_for_sse(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling ``main`` with host/port should mutate FastMCP settings before
    invoking ``mcp.run``. We stub ``mcp.run`` so we don't actually bind a
    socket in the unit-test process.
    """
    captured: dict[str, str | int | None] = {}

    def fake_run(*, transport: str = "stdio") -> None:
        captured["transport"] = transport
        captured["host"] = server.mcp.settings.host
        captured["port"] = server.mcp.settings.port

    monkeypatch.setattr(server.mcp, "run", fake_run)
    server.main(transport="sse", host="0.0.0.0", port=12345)

    assert captured["transport"] == "sse"
    assert captured["host"] == "0.0.0.0"
    assert captured["port"] == 12345


def test_main_does_not_mutate_settings_when_args_omitted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Stdio transport with no host/port shouldn't touch FastMCP settings."""
    original_host = server.mcp.settings.host
    original_port = server.mcp.settings.port

    captured: dict[str, str] = {}

    def fake_run(*, transport: str = "stdio") -> None:
        captured["transport"] = transport

    monkeypatch.setattr(server.mcp, "run", fake_run)
    server.main()

    assert captured["transport"] == "stdio"
    assert server.mcp.settings.host == original_host
    assert server.mcp.settings.port == original_port
