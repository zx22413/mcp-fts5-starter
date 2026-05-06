"""Synthetic-corpus benchmark for ``mcp-fts5-starter``.

Generates corpora of varying sizes, indexes them with the default
``unicode61`` tokenizer, and measures:

- Index build time (cold rebuild)
- Query latency (p50/p95/p99 over a fixed query set)
- DB size on disk
- Peak Python heap during index build (tracemalloc)

Run::

    uv run python scripts/benchmark.py

Defaults to corpus sizes [100, 1000, 10000]. Override with ``--sizes``::

    uv run python scripts/benchmark.py --sizes 1000 10000 50000

The script is hermetic — it builds everything inside a tmp dir and
cleans up. Set ``--keep`` to leave the output dir for inspection.

Output format is markdown so you can pipe it straight into
``docs/benchmark.md``::

    uv run python scripts/benchmark.py --markdown >> docs/benchmark.md
"""

from __future__ import annotations

import argparse
import random
import shutil
import statistics
import sys
import tempfile
import time
import tracemalloc
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

from mcp_fts5_starter.ingest import rebuild  # noqa: E402
from mcp_fts5_starter.search import SearchDB  # noqa: E402

VOCAB = (
    "search index ranking corpus document tokenize segment query keyword "
    "phrase vector embedding fusion BM25 RRF FTS5 SQLite Python markdown "
    "frontmatter sync incremental rebuild update delete protocol stdio "
    "transport server client tool function module schema table column "
    "weight title summary content tag type hash unicode latin chinese "
    "japanese korean script tokenizer fallback fixture benchmark latency "
    "throughput memory peak persistent ephemeral commit transaction journal"
).split()

QUERIES = [
    "BM25 weights",
    "vector embedding fusion",
    "incremental sync",
    "tokenizer",
    "schema",
    "FTS5 ranking",
    "markdown frontmatter",
    "search latency",
    "Python module",
    "rebuild index",
    "transport server",
    "fallback fixture",
    "Chinese script",
    "RRF",
    "tag weight title",
]


@dataclass(frozen=True)
class Result:
    size: int
    tokenizer: str
    index_seconds: float
    db_bytes: int
    peak_heap_bytes: int
    p50_ms: float
    p95_ms: float
    p99_ms: float


def synth_doc(i: int, rng: random.Random) -> tuple[str, str]:
    title_words = rng.sample(VOCAB, 4)
    title = " ".join(title_words).title()
    n_paragraphs = rng.randint(3, 8)
    paragraphs = []
    for _ in range(n_paragraphs):
        n_words = rng.randint(40, 120)
        paragraphs.append(" ".join(rng.choices(VOCAB, k=n_words)))
    tags = rng.sample(VOCAB, 3)
    body = (
        f"---\n"
        f"title: {title}\n"
        f"created: 2026-05-{(i % 28) + 1:02d}\n"
        f"tags:\n"
        + "".join(f"  - {t}\n" for t in tags)
        + "---\n\n"
        f"## Summary\n\n{paragraphs[0][:200]}\n\n"
        + "\n\n".join(paragraphs[1:])
    )
    return f"doc_{i:06d}.md", body


def write_corpus(root: Path, size: int, seed: int = 42) -> None:
    rng = random.Random(seed)
    notes = root / "notes"
    notes.mkdir(parents=True, exist_ok=True)
    for i in range(size):
        name, body = synth_doc(i, rng)
        (notes / name).write_text(body, encoding="utf-8")


def measure(size: int, tokenizer: str) -> Result:
    with tempfile.TemporaryDirectory(prefix="mcpfts5-bench-") as tmp:
        tmp_path = Path(tmp)
        corpus = tmp_path / "corpus"
        write_corpus(corpus, size)
        db_path = tmp_path / "index.db"

        tracemalloc.start()
        t0 = time.perf_counter()
        with SearchDB(db_path, tokenizer=tokenizer) as db:
            stats = rebuild(db, corpus)
        index_seconds = time.perf_counter() - t0
        peak_heap = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        assert stats.total == size, f"expected {size}, indexed {stats.total}"

        db_bytes = db_path.stat().st_size

        # Warm-up + measured pass.
        latencies_ms: list[float] = []
        with SearchDB(db_path, tokenizer=tokenizer) as db:
            for q in QUERIES:
                db.search(q, limit=10)
            for q in QUERIES * 3:
                t1 = time.perf_counter()
                db.search(q, limit=10)
                latencies_ms.append((time.perf_counter() - t1) * 1000)

        return Result(
            size=size,
            tokenizer=tokenizer,
            index_seconds=index_seconds,
            db_bytes=db_bytes,
            peak_heap_bytes=peak_heap,
            p50_ms=statistics.median(latencies_ms),
            p95_ms=_percentile(latencies_ms, 0.95),
            p99_ms=_percentile(latencies_ms, 0.99),
        )


def _percentile(values: list[float], p: float) -> float:
    s = sorted(values)
    k = int(round(p * (len(s) - 1)))
    return s[k]


def fmt_bytes(b: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if b < 1024:
            return f"{b:.1f} {unit}"
        b //= 1024
    return f"{b:.1f} TB"


def render_markdown(results: list[Result]) -> str:
    lines = [
        "| Corpus size | Tokenizer | Index time | Index throughput | DB size | Peak heap | Query p50 | Query p95 | Query p99 |",
        "|------------:|-----------|-----------:|-----------------:|--------:|----------:|----------:|----------:|----------:|",
    ]
    for r in results:
        throughput = r.size / r.index_seconds if r.index_seconds > 0 else 0
        lines.append(
            f"| {r.size:>8,} | {r.tokenizer:<9} | {r.index_seconds:>7.2f} s | "
            f"{throughput:>7,.0f} doc/s | {fmt_bytes(r.db_bytes):>7} | "
            f"{fmt_bytes(r.peak_heap_bytes):>7} | "
            f"{r.p50_ms:>6.2f} ms | {r.p95_ms:>6.2f} ms | {r.p99_ms:>6.2f} ms |"
        )
    return "\n".join(lines)


def render_text(results: list[Result]) -> str:
    return render_markdown(results)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark", description=__doc__)
    parser.add_argument(
        "--sizes",
        type=int,
        nargs="+",
        default=[100, 1000, 10000],
        help="Corpus sizes to benchmark. Default: 100 1000 10000.",
    )
    parser.add_argument(
        "--tokenizers",
        nargs="+",
        default=["unicode61"],
        help='Tokenizers to test. "jieba" requires the [jieba] extra installed.',
    )
    parser.add_argument(
        "--markdown",
        action="store_true",
        help="Print just the markdown table (no header).",
    )
    args = parser.parse_args(argv)

    if not args.markdown:
        print("# mcp-fts5-starter benchmark\n")
        print(f"Sizes: {args.sizes}")
        print(f"Tokenizers: {args.tokenizers}")
        print("Queries per size: 45 (15 unique × 3 passes after warm-up)\n")

    results: list[Result] = []
    for tokenizer in args.tokenizers:
        for size in args.sizes:
            if not args.markdown:
                print(f"... measuring size={size} tokenizer={tokenizer} ...", file=sys.stderr)
            results.append(measure(size, tokenizer))

    print(render_markdown(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
