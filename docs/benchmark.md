# Benchmark

A reproducible synthetic-corpus benchmark for `mcp-fts5-starter`. The methodology, the script, and the numbers — so the architecture doc's [comparison table](architecture.md#comparison-when-each-option-wins) doesn't have to bluff.

> Numbers below are from a single run on a developer laptop (Windows 11, Python 3.10.6, SQLite 3.x via stdlib). Reproduce locally with `uv run python scripts/benchmark.py`. Hardware effects dominate at small scales — treat the relative shape, not the absolute numbers, as the takeaway.

## Results

| Corpus size | Tokenizer | Index time | Throughput | DB size | Peak Python heap | Query p50 | Query p95 | Query p99 |
|------------:|-----------|-----------:|-----------:|--------:|-----------------:|----------:|----------:|----------:|
|         100 | unicode61 |     1.03 s | 97 doc/s   |  676 KB |           202 KB |   0.38 ms |   0.61 ms |   0.68 ms |
|       1,000 | unicode61 |    13.04 s | 77 doc/s   |    5 MB |             1 MB |   7.20 ms |   8.78 ms |   8.98 ms |
|      10,000 | unicode61 |   241.34 s | 41 doc/s   |   58 MB |            14 MB |  49.20 ms |  58.03 ms |  66.17 ms |

### How to read it

- **100–1,000 docs is the sweet spot.** Sub-millisecond p50 search at 100 docs, single-digit milliseconds at 1k. This is the personal-corpus target — the starter does what it says on the tin.
- **10k docs still works as an interactive tool.** 50 ms p50 search is well under the perceived-instant threshold (~100 ms). Ingest is slow enough that you should rely on incremental `sync` — don't `rebuild` on every keystroke.
- **Beyond 10k, look elsewhere.** Ingest throughput degrades (FTS5's per-document segment work scales sub-linearly), DB size grows, and you stop being a "starter" use case. Meilisearch / OpenSearch / Qdrant / managed equivalents earn their keep.
- **Memory is bounded.** Even at 10k docs the Python heap stays at ~14 MB. SQLite's own page cache is on top of that; both are tiny relative to anything else in a Python process.

## What the benchmark caught: the per-doc commit bug

This is the kind of finding that pays for the time spent writing a benchmark in the first place. Before the optimization documented in commit `<commit-sha>`, `SearchDB.upsert` called `self.conn.commit()` after every single insert. Each commit triggered a journal-mode fsync — about 30–40 ms on a Windows NTFS volume. For a 10k-doc rebuild that's ~10,000 fsyncs.

Result on the same hardware:

| Corpus size | Before fix (per-doc commit) | After fix (batched + WAL) | Speedup |
|------------:|----------------------------:|---------------------------:|--------:|
|         100 |                       2.09 s |                      1.03 s |    2.0× |
|       1,000 |                      17.73 s |                     13.04 s |    1.4× |
|      10,000 |                     439.53 s |                    241.34 s |    1.8× |

The fix:

- `SearchDB.upsert(commit=True)` and `SearchDB.delete(commit=True)` gain a `commit` keyword. Default stays `True` for callers writing one document at a time.
- `ingest.sync` and `ingest.rebuild` pass `commit=False` in the loop and call a single `db.commit()` at the end.
- `schema.connect` enables `PRAGMA journal_mode=WAL` and `PRAGMA synchronous=NORMAL`. WAL is the modern SQLite default for read-heavy applications; `synchronous=NORMAL` survives a process crash but trades power-loss durability for throughput, which is the right call for an index you can always rebuild.

This shows up in the API as a `commit=False` knob you'd otherwise never see — but anyone calling `SearchDB.upsert` in their own loop now gets the same headroom.

## Methodology

The benchmark generates a synthetic corpus where each document is:

- A YAML frontmatter block (`title`, `created`, `tags`)
- A `## Summary` section followed by 3–8 paragraphs of 40–120 words each
- Words drawn uniformly from a fixed 75-token vocabulary chosen to look like a search-domain corpus (`bm25`, `tokenize`, `embedding`, etc.)

Average doc size is ~3.5 KB. The vocabulary is intentionally narrow so the queries (15 fixed phrases run 3× each after a warm-up pass) actually hit a meaningful fraction of the corpus — wider vocab would make every query a one-liner and hide FTS5's per-doclist scan cost. Real-world recall numbers will look different; this is about engine behavior, not corpus quality.

Each measurement:

1. Generate corpus to a temp directory.
2. Start `tracemalloc`, time a cold rebuild, capture peak heap.
3. Open a fresh `SearchDB`, run all 15 queries once for warm-up.
4. Run all 15 queries 3 more times, capture per-query latency. Compute p50/p95/p99.
5. Tear down the temp directory.

The test process is single-threaded. Each corpus size is measured once — the script is deterministic via seed `42`, so reruns produce numbers within ~10% of each other on the same machine.

## What this benchmark intentionally doesn't measure

- **Recall and ranking quality.** Synthetic corpora make terrible relevance fixtures. The architecture doc's [comparison table](architecture.md#comparison-when-each-option-wins) summarizes the qualitative picture; a future benchmark with a real fixture (e.g. the BEIR datasets, or a sliced Wikipedia dump) is the right way to put numbers there.
- **Hybrid retrieval (BM25 + vector RRF).** Requires choosing an embedder, which means choosing dependencies and provider keys. Out of scope for the core repo's benchmark.
- **`jieba` tokenizer.** Worth a separate run with `--tokenizers unicode61 jieba` once the [jieba] extra is installed; the fixture's vocabulary is Latin so the difference would be measurement noise on this corpus anyway.
- **Cross-library comparison.** "FTS5 vs Meilisearch vs Qdrant" requires building three separate fixtures with three different ingestion paths and is its own multi-day project. The architecture doc's comparison table covers the qualitative shape.

## Reproduce

```bash
git clone https://github.com/zx22413/mcp-fts5-starter
cd mcp-fts5-starter
uv sync
uv run python scripts/benchmark.py
```

Output is markdown — pipe it back into this doc:

```bash
uv run python scripts/benchmark.py --markdown >> docs/benchmark.md
```

Custom sizes:

```bash
uv run python scripts/benchmark.py --sizes 1000 10000 50000
```

The script is hermetic — it builds everything in `tempfile.TemporaryDirectory()` and cleans up.

## Caveats

- **Single-machine, single-run.** Numbers will shift on different storage (SSD vs. NVMe vs. spinning disk vs. tmpfs), different OSes (Linux fsync is faster than Windows NTFS), and different SQLite versions. Don't paste these into a vendor comparison.
- **No GIL contention measured.** Single-threaded by construction. A real MCP server with concurrent tool calls might see different numbers; FastMCP's stdio transport is also serialized so this is mostly representative.
- **Index time at 10k+ is the limiting factor today.** PRAGMA tuning beyond what we already do (WAL + synchronous=NORMAL) is on the v0.3 wishlist — most likely a `bulk_load()` context manager that turns off journaling for the duration of a `rebuild`. Not worth the complexity for the typical user.
