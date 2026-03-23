# RAG Operations Dashboard

**Demonstrating how to *operate* a RAG system in production — not just build one.**

This project is the observability and review layer on top of an n8n-powered ingestion pipeline. Documents are ingested and embedded by n8n workflows, stored in a self-hosted Supabase instance, and monitored here.

---

## What This Demonstrates

| Concept | Description |
|---|---|
| **Authority Scoring** | Every document scores 0.0–1.0 based on source type. Scores decay over time via exponential decay (half-life: 7 days). |
| **Conflict Detection** | A daily n8n SQL node finds chunk pairs from different documents with cosine similarity ≥ 0.88 and writes them to `quarantine_queue`. |
| **Quarantine Review** | Conflicting chunk pairs are reviewed side-by-side with approve/reject workflow. Already-reviewed pairs are never re-queued. |
| **Knowledge Decay** | Daily n8n SQL node applies `authority_score * 0.5^(1/7)` to all documents with score < 1.0. |
| **Combined Retrieval** | Final score = `α * semantic + β * recency + γ * authority`. Weights are tunable in the Search Playground. |

---

## Architecture

```
n8n (ingestion + scheduling)
  ├── Ingest documents → documents_pg (chunks + embeddings via text-embedding-3-small)
  ├── Upsert metadata  → document_metadata (title, url, authority_score)
  ├── Daily: conflict detection SQL → quarantine_queue
  └── Daily: authority score decay SQL → document_metadata

Streamlit Dashboard (this repo)
  └── Reads from Supabase (same instance as ai-stack)
```

---

## Dashboard Pages

- **Overview** — Live KPIs: document count, chunk count, avg health score, avg authority
- **Knowledge Health** — Per-document health table with color-coded scores
- **Conflict Detection** — Side-by-side review of conflicting chunk pairs with approve/reject
- **Quarantine Queue** — Pending conflicts sorted by similarity, with authority score comparison
- **Decay Simulation** — Simulate corpus health N months into the future
- **Search Playground** — Interactive retrieval with α/β/γ weight sliders

---

## Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| Database | Self-hosted Supabase (via [ai-stack](https://github.com/ThHutterer/ai-stack)) |
| Embeddings | OpenAI `text-embedding-3-small` (1536-dim, matches n8n) |
| Ingestion | n8n workflows |
| Connection | psycopg2 direct to Postgres |

---

## Setup

**1. Clone and install**
```bash
git clone https://github.com/ThHutterer/rag-ops
cd rag-ops
uv venv && uv pip install -r requirements.txt
```

**2. Configure environment**

```bash
cp .env.example .env
```

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=your_postgres_password

OPENAI_API_KEY=your_openai_key

CONFLICT_SIMILARITY_THRESHOLD=0.88
DECAY_HALF_LIFE_DAYS=7
```

Requires a running [ai-stack](https://github.com/ThHutterer/ai-stack) instance with the Supabase port exposed.

**3. Run the schema**

Run `schema.sql` once in the Supabase SQL editor to create `documents_pg`, `document_metadata`, and `quarantine_queue`.

**4. Launch**
```bash
streamlit run app/main.py
```

---

## n8n SQL Nodes

**Conflict Detection** (runs daily):
```sql
INSERT INTO quarantine_queue (chunk_id, conflict_chunk_id, similarity)
SELECT a.id, b.id, 1 - (a.embedding <=> b.embedding)
FROM documents_pg a
JOIN documents_pg b ON a.id < b.id
WHERE a.metadata->>'file_id' != b.metadata->>'file_id'
  AND 1 - (a.embedding <=> b.embedding) >= 0.88
  AND NOT EXISTS (
      SELECT 1 FROM quarantine_queue q
      WHERE (q.chunk_id = a.id AND q.conflict_chunk_id = b.id)
         OR (q.chunk_id = b.id AND q.conflict_chunk_id = a.id)
  )
ON CONFLICT (chunk_id, conflict_chunk_id) DO NOTHING;
```

**Authority Score Decay** (runs daily):
```sql
UPDATE document_metadata
SET authority_score = (authority_score::float * POWER(0.5, 1.0 / 7.0))::text
WHERE authority_score::float < 1;
```

---

## Project Structure

```
rag-ops/
├── ragops/             # Core library (config, embedder, chunker, authority, decay, ingestion, retrieval)
├── scripts/            # fetch_local_ki, run_decay, seed_db
├── app/
│   ├── main.py         # Landing page with live KPIs
│   └── pages/          # 5 dashboard pages
├── schema.sql          # Supabase schema
└── requirements.txt
```
