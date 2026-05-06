"""Tiny YAML frontmatter parser — handles the subset commonly seen in markdown.

We parse only the few fields a generic indexer needs (title, tags, created),
plus arbitrary scalar passthrough. No full YAML implementation; if you have a
more complex frontmatter, swap this for ``python-frontmatter``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Frontmatter:
    title: str = ""
    tags: tuple[str, ...] = ()
    created: str = ""
    extras: dict[str, str] = field(default_factory=dict)


_FRONTMATTER_BLOCK = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse(text: str) -> Frontmatter:
    """Parse the leading ``---`` block of a markdown document.

    Returns an empty Frontmatter if no block is present.
    """
    match = _FRONTMATTER_BLOCK.match(text)
    if not match:
        return Frontmatter()

    title = ""
    created = ""
    tags: list[str] = []
    extras: dict[str, str] = {}
    in_tags = False

    for raw in match.group(1).splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped:
            in_tags = False
            continue

        if in_tags and stripped.startswith("- "):
            tags.append(stripped[2:].strip().strip("\"'"))
            continue

        in_tags = False
        if ":" not in stripped:
            continue
        key, _, value = stripped.partition(":")
        key = key.strip()
        value = value.strip().strip("\"'")

        if key == "title":
            title = value
        elif key == "created":
            created = value
        elif key == "tags":
            if value:
                tags.extend(_inline_list(value))
            else:
                in_tags = True
        else:
            if value:
                extras[key] = value

    return Frontmatter(
        title=title,
        tags=tuple(tags),
        created=created,
        extras=extras,
    )


def _inline_list(value: str) -> list[str]:
    """Parse an inline YAML list like ``[a, b, c]``."""
    if value.startswith("[") and value.endswith("]"):
        return [v.strip().strip("\"'") for v in value[1:-1].split(",") if v.strip()]
    return [value]


def strip(text: str) -> str:
    """Return the document body with frontmatter removed."""
    match = _FRONTMATTER_BLOCK.match(text)
    if not match:
        return text
    return text[match.end() :]
