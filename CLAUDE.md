# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# rag-ops

RAG Operations Dashboard — demonstrates how to *operate* a RAG system in production, not just build one.

Most RAG demos show ingestion and retrieval. This project shows what happens after: staleness detection, conflict resolution, authority scoring, and knowledge decay. The data layer uses real public sources (Metaculus + RSS news) to create genuine, demonstrable conflicts — not synthetic examples.

**Portfolio target:** Senior AI / AI Transformation Lead roles in enterprise contexts.

---

## Core Concepts (Read Before Coding)

### Authority Score
Every chunk has an authority score (0.0–1.0) derived from its source type and review status. Metaculus resolved questions = 1.0 and are immune to decay. News articles = ~0.5 and decay over time.

```
metaculus (resolved) > arxiv_paper > news_article
```

### Combined Retrieval Score
Retrieval is NOT pure cosine similarity. Final score = weighted combination:
```
score = α * semantic_similarity + β * recency + γ * (authority * decay)
```
Weights α/β/γ are tunable and exposed in the Search Playground UI.

### Conflict Detection
On every ingestion, new chunks are compared against existing ones. If similarity > threshold AND the source document differs → quarantine flag. Special case: if the conflicting chunk comes from a resolved Metaculus question → flagged as `"falsified_by_resolution"`, not just `"semantic_overlap"`.

### Decay
Exponential decay on `chunks.decay_score` based on days since `last_modified`. Half-life = 180 days (configurable). Metaculus chunks never decay. Decay does NOT delete chunks — only reduces their retrieval score.

---

## Commands

```bash
pip install -r requirements.txt          # install all dependencies

python scripts/seed_db.py               # fetch + embed + store all data (run once)
python scripts/fetch_metaculus.py       # fetch Metaculus questions only
python scripts/fetch_news_rss.py        # fetch RSS articles only
python scripts/run_decay.py             # apply decay pass to chunks in DB
python scripts/simulate_retrievals.py  # populate retrieval_log for demo realism

streamlit run app/main.py              # launch the dashboard
```

No build step, no Docker. Supabase is cloud; everything else is pip.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| UI | Streamlit | Python-only, sufficient for portfolio |
| Logic | Python modules | No FastAPI needed — Streamlit calls Supabase directly |
| Vector DB | Supabase pgvector (Cloud Free Tier) | User knows Supabase well |
| Metadata | Supabase Postgres (same instance) | Single DB, no SQLite |
| Embeddings | `sentence-transformers` `all-MiniLM-L6-v2` | Local, no API key needed |
| Config | `.env` via `python-dotenv` | Standard |

**No Docker.** Supabase is cloud. Everything else is `pip install`.  
**Python only.** No TypeScript, no FastAPI, no React.

---

## Project Structure

```
rag-ops/
├── CLAUDE.md                   ← this file (always loaded by Claude Code)
├── PLAN.md                     ← agent build order, contracts, validation scripts
├── README.md
├── schema.sql                  ← run once in Supabase SQL editor
├── .env.example
├── .gitignore
├── requirements.txt
│
├── ragops/
│   ├── __init__.py
│   ├── config.py               ← Supabase client + env loading
│   ├── embedder.py             ← sentence-transformers wrapper
│   ├── chunker.py              ← sliding window text chunker
│   ├── authority.py            ← authority_score computation
│   ├── decay.py                ← exponential decay formula
│   ├── ingestion.py            ← ingest → embed → upsert → conflict check
│   └── retrieval.py            ← combined scoring search
│
├── scripts/
│   ├── fetch_metaculus.py      ← Metaculus API → resolved questions into DB
│   ├── fetch_news_rss.py       ← RSS feeds → news articles into DB
│   ├── seed_db.py              ← orchestrates fetchers + ingestion pipeline
│   ├── run_decay.py            ← apply decay pass to all chunks in DB
│   └── simulate_retrievals.py  ← populate retrieval_log for demo realism
│
└── app/
    ├── main.py                 ← Streamlit entry point
    └── pages/
        ├── 1_Knowledge_Health.py
        ├── 2_Conflict_Detection.py
        ├── 3_Quarantine_Queue.py
        ├── 4_Decay_Simulation.py
        └── 5_Search_Playground.py
```

---

## Supabase Schema

Enable pgvector first:
```sql
create extension if not exists vector;
```

### `documents`
```sql
CREATE TABLE documents (
    id                        uuid primary key default gen_random_uuid(),
    title                     text not null,
    source_type               text not null,       -- metaculus | news_article | arxiv_paper
    author                    text,
    created_at                timestamptz,
    last_modified             timestamptz,
    review_status             text,                -- resolved | published | preprint
    authority_score           float,
    url                       text,
    metaculus_question_id     int,
    metaculus_resolution      text,                -- YES | NO | numeric | null
    metaculus_resolution_date timestamptz
);
```

### `chunks`
```sql
CREATE TABLE chunks (
    id              uuid primary key default gen_random_uuid(),
    document_id     uuid references documents(id) on delete cascade,
    content         text not null,
    embedding       vector(384),
    chunk_index     int,
    retrieval_count int default 0,
    flagged         boolean default false,
    flag_reason     text,
    decay_score     float default 1.0,
    created_at      timestamptz default now()
);
```

### `quarantine_queue`
```sql
CREATE TABLE quarantine_queue (
    id                uuid primary key default gen_random_uuid(),
    chunk_id          uuid references chunks(id),
    conflict_chunk_id uuid references chunks(id),
    similarity        float,
    reason            text,    -- semantic_overlap | falsified_by_resolution
    status            text default 'pending',   -- pending | approved | rejected
    created_at        timestamptz default now(),
    reviewed_at       timestamptz
);
```

### `retrieval_log`
```sql
CREATE TABLE retrieval_log (
    id           uuid primary key default gen_random_uuid(),
    query        text,
    chunk_ids    uuid[],
    retrieved_at timestamptz default now(),
    feedback     text    -- null | good | bad
);
```

---

## Authority Score Logic

```python
# ragops/authority.py
SOURCE_TYPE_SCORES = {
    "metaculus":    1.0,
    "arxiv_paper":  0.75,
    "news_article": 0.5,
}
REVIEW_STATUS_MULTIPLIER = {
    "resolved":  1.0,
    "published": 0.85,
    "preprint":  0.7,
}
# Metaculus resolved chunks: decay_score locked at 1.0 permanently
```

---

## Data Sources

**Metaculus API** (no auth required):
```
GET https://www.metaculus.com/api2/questions/?status=resolved&limit=100
```
Target: ~100–200 resolved questions on AI / tech / science topics.

**RSS Feeds:**
```python
RSS_FEEDS = [
    "https://feeds.feedburner.com/oreilly/radar",
    "https://rss.arxiv.org/rss/cs.AI",
    "https://www.technologyreview.com/feed/",
    "https://feeds.arstechnica.com/arstechnica/technology-lab",
]
```

---

## Scope Boundaries — Do NOT Build

- No authentication or user management
- No LLM calls (embeddings only — keeps repo free to clone and run)
- No Docker
- No FastAPI layer
- No live polling / continuous sync — seed once, demo from snapshot
- No scraping behind paywalls — RSS summary text is sufficient

---

## Environment Variables

```
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_DB_URL=postgresql://postgres:password@db.your-project.supabase.co:5432/postgres

CONFLICT_SIMILARITY_THRESHOLD=0.88
DECAY_HALF_LIFE_DAYS=180
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

---

## Requirements

```
streamlit
supabase
psycopg2-binary
sentence-transformers
python-dotenv
pandas
plotly
numpy
feedparser
requests
```
