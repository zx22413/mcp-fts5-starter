# 一個給 Claude 用的、無聊但夠用的中間值搜尋後端

> [English](launch.md) | 繁體中文

過去一年我看過的「給筆記做 RAG」教學幾乎都是同一套 stack：embedding model + vector database + 500MB Docker image。但對一個放著幾千份 markdown、給單一使用者、跑在單一機器上的個人語料庫來說，這太重了——而且教學結束之後，那些維運成本會永遠跟著你。

我剛 release 了 [`mcp-fts5-starter`](https://github.com/zx22413/mcp-fts5-starter) v0.1.0——一個用 SQLite FTS5 做全文搜尋的 drop-in MCP server 模板。三百行 source、不需要額外服務、一台 Pi 就跑得動。`pip install` 完 Claude Code 立刻可以串上來。

這篇文章在講三件事：FTS5 為什麼明明該是預設選項卻沒人這樣放、我從哪個維持了 18 個月的上游專案把它拆出來、還有兩次 embedding 換代之前我自己埋的一個 bug——現在以「防禦性 log」的形式被保留在新 repo 裡。

## 主張：FTS5 在大部分情況下夠用

三件事同時成立：

- **向量搜尋確實有用。** 改寫過的句子、縮寫、翻譯——關鍵字匹配跨不過任何一道。
- **向量搜尋對大多數個人語料庫來說是錯的預設值。** 幾千份 markdown 不需要 24/7 的語意檢索服務。它們需要的是毫秒級、零維運的關鍵字搜尋。
- **兩者之間的橋接是已知問題。** Reciprocal Rank Fusion 是一段話就能寫完的程式碼，把 BM25 的 rank 跟向量 cosine similarity 的 rank 融合起來。從「只用 BM25」升級到「混合檢索」不需要改 data model。

這個 starter 認真對待這三件事。它預設只有 FTS5——沒有 embedding、沒有 provider key、沒有 token 預算。schema 預先建好一個 `notes_vec` 表，裡面是空的，直到你接上 embedder。ranker 已經會做 RRF fusion；只是還沒東西可以 fuse。等到 BM25 不夠用的那一天——對很多語料庫來說，那一天永遠不會到——升級就是一個 30 行的 adapter 檔，不是 migration。

形狀跟你提早幾年在 DB driver 前面包一層 interface 一樣：現在的代價接近零、未來的選擇權很大、今天不需要的東西今天就不付錢。

## 拆出來的時候砍掉了什麼

這個 starter 是 `brain-knowledge-base` 的剝皮版。後者是我自己的 closed-source MCP server，過去 18 個月一直接著我的 Obsidian vault 在跑。三件東西必須拿掉。

**1. Memory decay。** 上游有一套三層遺忘系統（`heat_score`、`level`、archive 表）——沒人搜尋的舊筆記會遷移到比較冷的索引。那是另一個問題領域，現在住在昨天 ship 的姊妹 repo [`forget-rag`](https://github.com/zx22413/forget-rag)。兩個 repo 的 README 互相 link：要 decay？去那邊。要 starter？留這。

**2. Domain tools。** 上游有 ~14 個 MCP tool 全部跟我 vault 的結構綁死：`save_clipping`、`list_concepts`、`get_backlinks`、`save_session_summary`、`send_telegram`。對我有用、對別人沒用。換成四個 generic 工具：`search`、`list`、`read`、`index`。`doc_type` 參數——預設用每個檔案的父資料夾名稱——讓任何人都有 built-in 的 faceted filter，不用先宣告 schema。

**3. Personalization。** Concept 提及追蹤、tag affinity 加成、用 `claude -p` 在每個 session 存檔時自動插 wikilink 的步驟。全部都聰明、全部都跟我的 workflow 綁死、全部都不該放在 starter 裡。

結果是 ~3× 小（~700 行 vs. 上游 ~1700 行）、可以一坐看完——這就是 starter 的意義。

## 那個讓我加上 dim check 的 bug

starter 裡我最自豪的防禦性程式碼是六行：

```python
if len(vec) != query_dim:
    logger.warning(
        "vec dim mismatch (stored=%d, query=%d) at path=%s — re-index needed",
        len(vec),
        query_dim,
        row[0],
    )
    continue
```

它存在的原因是我幾個月前 ship 給自己用的一個真實 bug。

上游一開始用的是 local Ollama 跑 `bge-m3`，1024 維向量。一切正常、搜尋好用、人生美滿。後來 Gemini 的 `gemini-embedding-001` 便宜到我決定 migrate——中文 phrasing 的 recall 更好，又不用 babysit Ollama daemon。1536 維。我把 `EMBEDDING_PROVIDER=gemini` 一翻、重啟、跑了幾個測試 query、結果回來感覺隱約有點怪但又沒明顯錯。聳聳肩、忘了。

幾週之後我發現搜尋對某些以前能精準命中的 query，開始回傳不相關的筆記。花了半個晚上 grep 排序邏輯找哪個 hyperparameter 過期了。真正的 bug：cosine similarity 是用 `zip(query_vec, stored_vec)` 算的——而 `zip()` 會靜默截斷到比較短的那邊。全新的 1536 維 query 向量被拿去跟存好的 1024 維向量的「前 1024 維」比。數字還是算得出來。數字是垃圾。搜尋優雅地降級成噪音。

上游的修法是一個一次性的 migration script（`migrate_embeddings_to_gemini.py`）把全部重 embed。Starter 的修法是上面那個 dim check——存好的 vector 跟現在的 query embedder 維度不同就大聲跳過。Architecture doc 對應加了一句：**「換 embedder 之後跑 `rebuild`。任何 stored token 或 vector 不再能跟新產出物比較的場合，唯一安全的選擇是全量重建索引。」**

我一直在重學的教訓：靜默的 type coercion 比 crash 更糟。`zip()` 截短是 Python 上正確的語意、是這份工作上錯的工具。`zip(strict=True)` 第一次比較就會 raise，可以幫我省下三週的、隱性錯誤的搜尋結果。

## 怎麼試

```bash
git clone https://github.com/zx22413/mcp-fts5-starter
cd mcp-fts5-starter
uv sync
python scripts/build-sample.py
```

build script 會 index 七篇兼當文件的合成 markdown（FTS5、BM25、RRF、MCP、tokenization、why-not-vectors、incremental indexing）然後跑三個代表性的搜尋。從頭到尾大約十秒。

要把它接到 Claude Code 用 [`examples/claude-code/`](../../examples/claude-code/) 的 `.mcp.json` snippet，模型就有了 `search`、`list`、`read`、`index` 四個工具，可以對你指定的任何 markdown 資料夾搜尋。或是跳過 SDK，用 [`examples/raw-jsonrpc/demo.py`](../../examples/raw-jsonrpc/demo.py) 直接打 raw JSON-RPC over stdio——它會把每筆 wire message 印出來，協議從此不再是黑盒子。

如果你的語料庫主要是中文，`pip install mcp-fts5-starter[jieba]` 加上 `MCP_FTS5_TOKENIZER=jieba` 來啟用 pre-segmentation。如果你超過了 BM25 的負荷，實作只有一個 method 的 `Embedder` Protocol 然後 pass 給 `SearchDB`——schema 跟 ranker 一直在那邊等你。

## 接下來

這個 starter 刻意不是一張產品 roadmap。它是一個刻意小到能一坐讀完的 v0.1.0、把選擇權預先 bake 進你之後可能需要的部分。接下來的小版本會 land：

- 真實 benchmark fixture 進 `docs/benchmark.md`，可重現的數字（architecture doc 沒有捏造比較表——只有定性版本）。
- `Embedder` 接真實 provider 的範例，獨立成小 repo 讓 core 維持輕量。
- HTTP+SSE transport for hosted deployment。

在那之前：pip install、指向一個資料夾、停止為你不需要的東西付錢。

---

[`mcp-fts5-starter` on GitHub](https://github.com/zx22413/mcp-fts5-starter) · [PyPI](https://pypi.org/project/mcp-fts5-starter/) · [architecture doc](../architecture.md) · [`forget-rag`](https://github.com/zx22413/forget-rag)（姊妹 repo，做 memory decay）
