"""Smoke test — package imports and version is set."""

import mcp_fts5_starter


def test_version() -> None:
    assert mcp_fts5_starter.__version__ == "0.2.0"
