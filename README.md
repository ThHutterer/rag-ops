# RAG Operations Dashboard

**Demonstrating how to *operate* a RAG system in production — not just build one.**

Most RAG demos show ingestion and retrieval. This project shows what happens after: staleness detection, conflict resolution, authority scoring, and knowledge decay. The data layer uses real public sources (Metaculus + RSS news) to create genuine, demonstrable conflicts — not synthetic examples.

---

## What This Demonstrates

| Concept | Description |
|---|---|
| **Authority Scoring** | Every chunk scores 0.0–1.0 based on source type and review status. Metaculus resolved questions = 1.0, news articles ≈ 0.5. |
| **Conflict Detection** | On ingestion, new chunks are compared against existing ones via pgvector cosine similarity. Conflicts are quarantined with reason: `semantic_overlap` or `falsified_by_resolution`. |
| **Knowledge Decay** | Exponential decay on chunk scores based on days since last modified. Half-life = 180 days. Metaculus chunks are immune. |
| **Combined Retrieval** | Final score = `α * semantic + β * recency + γ * (authority × decay)`. Weights are tunable in the Search Playground. |

---

## Dashboard Pages

- **Overview** — Live corpus KPIs: document count, chunk count, avg decay score, flagged chunks, pending conflicts
- **Knowledge Health** — Per-document health table with color-coded scores
- **Conflict Detection** — Side-by-side review of conflicting chunks with approve/reject workflow
- **Quarantine Queue** — Full conflict resolution history with filtering and trend chart
- **Decay Simulation** — Slider to simulate corpus health N months into the future
- **Search Playground** — Interactive retrieval with α/β/γ weight sliders and score breakdown per result

---

## Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| Vector DB | Supabase pgvector |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` (local, no API key) |
| Data | Metaculus API + RSS (arXiv, MIT Tech Review, Ars Technica, ORF News) |

No Docker. No LLM calls. Runs entirely on `pip install`.

---

## Setup

**1. Clone and install**
```bash
git clone https://github.com/ThHutterer/rag-ops
cd rag-ops
uv venv && uv pip install -r requirements.txt
```

**2. Configure Supabase**

Create a free project at [supabase.com](https://supabase.com), run `schema.sql` in the SQL editor, then copy your credentials:

```bash
cp .env.example .env
# fill in SUPABASE_URL and SUPABASE_KEY
```

**3. Seed the database**
```bash
python scripts/seed_db.py --limit 100
python scripts/simulate_retrievals.py
```

**4. Launch**
```bash
streamlit run app/main.py
```

---

## Data Sources

- [Metaculus](https://www.metaculus.com) — resolved forecasting questions (AI, tech, science)
- [arXiv cs.AI](https://arxiv.org/list/cs.AI/recent) — latest AI preprints
- [MIT Technology Review](https://www.technologyreview.com)
- [Ars Technica](https://arstechnica.com/information-technology/)
- [ORF News](https://rss.orf.at/news.xml) — Austrian public broadcaster

---

## Project Structure

```
rag-ops/
├── ragops/             # Core library (config, embedder, chunker, authority, decay, ingestion, retrieval)
├── scripts/            # seed_db, fetch_metaculus, fetch_news_rss, run_decay, simulate_retrievals
├── app/
│   ├── main.py         # Landing page with live KPIs
│   └── pages/          # 5 dashboard pages
├── schema.sql          # Supabase schema + pgvector RPC functions
└── requirements.txt
```
