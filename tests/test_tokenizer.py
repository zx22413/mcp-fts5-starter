"""Tokenizer resolution tests."""

from __future__ import annotations

import importlib

import pytest

from mcp_fts5_starter import tokenizer as tk


def test_passthrough_returns_input() -> None:
    assert tk.passthrough("hello world") == "hello world"
    assert tk.passthrough("") == ""


def test_resolve_default_is_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_FTS5_TOKENIZER", raising=False)
    fn = tk.resolve()
    assert fn("hi") == "hi"


def test_resolve_unicode61_is_passthrough() -> None:
    fn = tk.resolve("unicode61")
    assert fn("hi") == "hi"


def test_resolve_jieba_raises_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """If jieba isn't installed, resolve('jieba') should raise a clear error."""
    if importlib.util.find_spec("jieba") is not None:
        pytest.skip("jieba is installed; can't test the missing-dep path")
    with pytest.raises(RuntimeError, match="jieba"):
        tk.resolve("jieba")
