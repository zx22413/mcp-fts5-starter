"""Frontmatter parser unit tests."""

from mcp_fts5_starter.frontmatter import parse, strip


def test_parse_block_form_tags() -> None:
    text = """---
title: Hello World
created: 2026-05-07
tags:
  - claude-code
  - dev-tools
---

Body text.
"""
    fm = parse(text)
    assert fm.title == "Hello World"
    assert fm.created == "2026-05-07"
    assert fm.tags == ("claude-code", "dev-tools")


def test_parse_inline_list_tags() -> None:
    text = """---
title: Inline tags
tags: [a, "b c", d]
---
"""
    fm = parse(text)
    assert fm.tags == ("a", "b c", "d")


def test_parse_quoted_title() -> None:
    text = '---\ntitle: "Foo: Bar"\n---\n\nbody'
    fm = parse(text)
    assert fm.title == "Foo: Bar"


def test_parse_extras_capture_unknown_keys() -> None:
    text = "---\ntitle: x\nsource: https://example.com/a\ntype: clipping\n---\n"
    fm = parse(text)
    assert fm.extras == {"source": "https://example.com/a", "type": "clipping"}


def test_parse_no_frontmatter_returns_empty() -> None:
    fm = parse("plain markdown\n\nno frontmatter")
    assert fm.title == ""
    assert fm.tags == ()
    assert fm.created == ""


def test_strip_removes_block() -> None:
    text = "---\ntitle: x\n---\n\nBody.\n"
    assert strip(text) == "Body.\n"


def test_strip_no_block_returns_unchanged() -> None:
    text = "no frontmatter here"
    assert strip(text) == text
