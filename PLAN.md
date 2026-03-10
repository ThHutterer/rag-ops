# rag-ops — Agent Build Plan

Execution blueprint for building with an agent team. Read CLAUDE.md first for project context, concepts, and schema.

---

## Agent Build Order & Communication

Agents MUST follow this contract-first sequence. No agent starts Phase N+1 until Phase N contract is verified by lead.

### Phase 1: Data Agent
1. Implement `scripts/fetch_metaculus.py` — Metaculus API fetch + insert into `documents` table
2. Implement `scripts/fetch_news_rss.py` — RSS fetch + insert into `documents` table
3. Implement `ragops/chunker.py` — sliding window chunker, returns `List[str]`
4. Implement `ragops/authority.py` — `compute_authority_score(source_type, review_status) → float`
5. Run validation (see below)
6. **Send contract to lead:** function signatures for `compute_authority_score`, chunker output format, and exact column names used in DB inserts

### Phase 2: Core RAG Agent (after receiving Phase 1 contract)
1. Implement `ragops/config.py` — Supabase client, load `.env`
2. Implement `ragops/embedder.py` — `embed(text: str) → List[float]`, `embed_batch(texts: List[str]) → List[List[float]]`
3. Implement `ragops/decay.py` — `compute_decay(days: int, half_life: int = 180) → float`
4. Implement `ragops/ingestion.py` — full pipeline: chunk → embed → upsert chunks → conflict detection → quarantine_queue writes
5. Implement `ragops/retrieval.py` — `search(query: str, alpha, beta, gamma, top_k) → List[dict]`
6. Implement `scripts/seed_db.py` — orchestrates Phase 1 fetchers + ingestion pipeline
7. Run validation (see below)
8. **Send contract to lead:** exact return shape of `search()`, exact quarantine_queue row structure, exact chunk upsert behavior

### Phase 3: Dashboard Agent (after receiving Phase 2 contract)
1. Implement `app/main.py` — Streamlit entry point, page config, sidebar nav
2. Implement all 5 pages in `app/pages/` (see Page Specs below)
3. Implement `scripts/simulate_retrievals.py` — populate `retrieval_log` for demo realism
4. Run validation (see below)

### Phase 4: Lead Validation
1. Contract diff — verify Phase 2 `search()` return shape matches what dashboard pages consume
2. Run `python scripts/seed_db.py` end-to-end
3. Run `streamlit run app/main.py` and walk through all 5 pages
4. Verify quarantine_queue has entries (conflict detection fired)
5. Verify at least one `"falsified_by_resolution"` conflict exists

---

## Cross-Cutting Concerns

| Concern | Owner | Detail |
|---|---|---|
| Metaculus decay immunity | Core RAG Agent | `decay_score` must be set to `1.0` and never updated for chunks where `documents.source_type = 'metaculus'` |
| Conflict reason enum | Core RAG Agent | Only two valid values: `"semantic_overlap"` and `"falsified_by_resolution"`. Dashboard filters on these exact strings. |
| Combined score weights | Core RAG Agent + Dashboard Agent | Weights α/β/γ default to `0.6 / 0.2 / 0.2`. Dashboard exposes sliders that pass these into `retrieval.search()` — signature must accept them as params. |
| Chunk upsert idempotency | Core RAG Agent | Re-running `seed_db.py` must not create duplicate chunks. Use document URL + chunk_index as deduplication key. |
| Retrieval count tracking | Core RAG Agent | Every call to `retrieval.search()` must increment `chunks.retrieval_count` for returned chunk IDs. |

---

## Function Contracts

### `ragops/embedder.py`
```python
def embed(text: str) -> List[float]:
    """Returns 384-dim embedding for all-MiniLM-L6-v2."""

def embed_batch(texts: List[str]) -> List[List[float]]:
    """Batch embed for efficiency during ingestion."""
```

### `ragops/authority.py`
```python
SOURCE_TYPE_SCORES = {"metaculus": 1.0, "arxiv_paper": 0.75, "news_article": 0.5}
REVIEW_STATUS_MULTIPLIER = {"resolved": 1.0, "published": 0.85, "preprint": 0.7}

def compute_authority_score(source_type: str, review_status: str) -> float:
    """Returns float 0.0–1.0."""
```

### `ragops/decay.py`
```python
def compute_decay(days_since_modified: int, half_life_days: int = 180) -> float:
    """Exponential decay. Returns 1.0 for metaculus source type (caller responsibility)."""
```

### `ragops/ingestion.py`
```python
def ingest_document(document_id: str) -> dict:
    """
    Fetches document from DB, chunks, embeds, upserts chunks.
    Runs conflict detection for each chunk.
    Returns: {"chunks_created": int, "conflicts_found": int}
    """
```

### `ragops/retrieval.py`
```python
def search(
    query: str,
    alpha: float = 0.6,
    beta: float = 0.2,
    gamma: float = 0.2,
    top_k: int = 5
) -> List[dict]:
    """
    Returns list of dicts with keys:
    {
        "chunk_id": str,
        "content": str,
        "combined_score": float,
        "semantic_score": float,
        "recency_score": float,
        "authority_decay_score": float,
        "source_type": str,
        "document_title": str,
        "authority_score": float,
        "decay_score": float,
        "flagged": bool,
        "retrieval_count": int
    }
    """
```

---

## Page Specs

### Page 1: `1_Knowledge_Health.py`
**Purpose:** Overview of corpus health.

Metric cards (top row):
- Total Chunks
- Avg Health Score (= avg of `authority_score * decay_score` across all chunks)
- Flagged Chunks count
- Pending Quarantine count

Main table (one row per document):
- `title`, `source_type`, `authority_score`, `avg_decay_score`, `chunk_count`, `total_retrieval_count`, `flagged_chunk_count`
- Color coding: green if avg_health > 0.7, yellow if 0.4–0.7, red if < 0.4

### Page 2: `2_Conflict_Detection.py`
**Purpose:** Review pending conflicts.

For each `quarantine_queue` entry with `status = 'pending'`:
- Two columns: Chunk A content | Chunk B content
- Below: similarity score, reason badge (`semantic_overlap` or `falsified_by_resolution`), source of each chunk
- Approve / Reject buttons → update `status` + `reviewed_at` in DB

### Page 3: `3_Quarantine_Queue.py`
**Purpose:** Full history of conflict resolution.

- Filter by status (pending / approved / rejected), date range
- Table: chunk preview, conflict reason, similarity, status, reviewed_at
- Line chart: resolution rate over time (approved + rejected per day)

### Page 4: `4_Decay_Simulation.py`
**Purpose:** Show how corpus health degrades over time.

- Slider: "Simulate X months into the future" (1–36)
- Applies `compute_decay()` to current `last_modified` dates with simulated future date
- Shows distribution of projected decay scores (histogram or bar chart)
- Highlights chunks that would fall below 0.3 threshold
- "Run actual decay pass" button → calls decay logic against live DB, updates `chunks.decay_score`

### Page 5: `5_Search_Playground.py`
**Purpose:** Interactive retrieval with weight tuning.

- Text input for query
- Sliders: α (semantic), β (recency), γ (authority×decay) — all 0.0–1.0, default 0.6/0.2/0.2
- Top-5 results displayed as cards:
  - Content (first 300 chars)
  - Score breakdown: combined | semantic | recency | authority×decay
  - Source type badge, document title, authority score, decay score
  - "Flag this chunk" button → sets `chunks.flagged = true`, shows reason input

---

## Validation Scripts

### Phase 1 Validation (Data Agent)

```bash
# Test Metaculus fetch (dry run — don't insert)
python -c "
from scripts.fetch_metaculus import fetch_resolved_questions
questions = fetch_resolved_questions(limit=5, dry_run=True)
assert len(questions) == 5
assert all('resolution' in q for q in questions)
print('✓ Metaculus fetch works, got', len(questions), 'questions')
"

# Test RSS fetch (dry run)
python -c "
from scripts.fetch_news_rss import fetch_articles
articles = fetch_articles(dry_run=True)
assert len(articles) > 0
assert all('title' in a and 'content' in a for a in articles)
print('✓ RSS fetch works, got', len(articles), 'articles')
"

# Test chunker
python -c "
from ragops.chunker import chunk_text
chunks = chunk_text('This is a test document. ' * 50, chunk_size=200, overlap=50)
assert len(chunks) > 1
assert all(isinstance(c, str) for c in chunks)
print('✓ Chunker works, produced', len(chunks), 'chunks')
"

# Test authority scores
python -c "
from ragops.authority import compute_authority_score
assert compute_authority_score('metaculus', 'resolved') == 1.0
assert compute_authority_score('news_article', 'published') < 0.5
assert compute_authority_score('arxiv_paper', 'preprint') < 0.75
print('✓ Authority scores correct')
"
```

### Phase 2 Validation (Core RAG Agent)

```bash
# Test embedder
python -c "
from ragops.embedder import embed, embed_batch
v = embed('test sentence')
assert len(v) == 384
batch = embed_batch(['one', 'two', 'three'])
assert len(batch) == 3
print('✓ Embedder works, dim =', len(v))
"

# Test decay
python -c "
from ragops.decay import compute_decay
assert compute_decay(0) == 1.0
assert 0.49 < compute_decay(180) < 0.51   # half-life at 180 days
assert compute_decay(360) < 0.26
print('✓ Decay formula correct')
"

# Test full seed pipeline (requires .env with real Supabase creds)
python scripts/seed_db.py --limit 10
python -c "
from ragops.config import get_supabase
sb = get_supabase()
docs = sb.table('documents').select('id').execute()
chunks = sb.table('chunks').select('id').execute()
assert len(docs.data) > 0, 'No documents inserted'
assert len(chunks.data) > 0, 'No chunks inserted'
print('✓ Seed pipeline: docs =', len(docs.data), ', chunks =', len(chunks.data))
"

# Test retrieval
python -c "
from ragops.retrieval import search
results = search('artificial intelligence progress', top_k=3)
assert len(results) <= 3
assert all('combined_score' in r for r in results)
assert all('content' in r for r in results)
print('✓ Retrieval works, top score:', results[0]['combined_score'] if results else 'no results')
"

# Test conflict detection fired
python -c "
from ragops.config import get_supabase
sb = get_supabase()
q = sb.table('quarantine_queue').select('id, reason').execute()
print('✓ Quarantine queue entries:', len(q.data))
reasons = set(r['reason'] for r in q.data)
print('  Reasons found:', reasons)
"
```

### Phase 3 Validation (Dashboard Agent)

```bash
# Streamlit syntax check (no browser needed)
python -m py_compile app/main.py && echo "✓ main.py valid"
python -m py_compile app/pages/1_Knowledge_Health.py && echo "✓ Page 1 valid"
python -m py_compile app/pages/2_Conflict_Detection.py && echo "✓ Page 2 valid"
python -m py_compile app/pages/3_Quarantine_Queue.py && echo "✓ Page 3 valid"
python -m py_compile app/pages/4_Decay_Simulation.py && echo "✓ Page 4 valid"
python -m py_compile app/pages/5_Search_Playground.py && echo "✓ Page 5 valid"

# Simulate retrieval log
python scripts/simulate_retrievals.py
python -c "
from ragops.config import get_supabase
sb = get_supabase()
logs = sb.table('retrieval_log').select('id').execute()
assert len(logs.data) > 0
print('✓ Retrieval log populated:', len(logs.data), 'entries')
"
```

### Phase 4 End-to-End Validation (Lead Agent)

```bash
# 1. Full seed run
python scripts/seed_db.py
echo "✓ Seed complete"

# 2. Verify corpus
python -c "
from ragops.config import get_supabase
sb = get_supabase()
docs = sb.table('documents').select('source_type').execute()
chunks = sb.table('chunks').select('id, decay_score, flagged').execute()
queue = sb.table('quarantine_queue').select('reason').execute()

source_types = set(d['source_type'] for d in docs.data)
assert 'metaculus' in source_types, 'No Metaculus documents'
assert 'news_article' in source_types, 'No news articles'

metaculus_chunks = [c for c in chunks.data if True]  # all chunks
flagged = [c for c in chunks.data if c['flagged']]
reasons = set(r['reason'] for r in queue.data)

print('✓ Documents:', len(docs.data), '| Source types:', source_types)
print('✓ Chunks:', len(chunks.data), '| Flagged:', len(flagged))
print('✓ Quarantine entries:', len(queue.data), '| Reasons:', reasons)
assert 'falsified_by_resolution' in reasons or 'semantic_overlap' in reasons, 'No conflicts detected'
print('✓ Conflict detection fired correctly')
"

# 3. Verify decay immunity for Metaculus chunks
python -c "
from ragops.config import get_supabase
sb = get_supabase()
# Get metaculus document IDs
meta_docs = sb.table('documents').select('id').eq('source_type', 'metaculus').execute()
meta_ids = [d['id'] for d in meta_docs.data]
# Check their chunks all have decay_score = 1.0
for doc_id in meta_ids[:5]:
    chunks = sb.table('chunks').select('decay_score').eq('document_id', doc_id).execute()
    for c in chunks.data:
        assert c['decay_score'] == 1.0, f'Metaculus chunk has decay < 1.0: {c[\"decay_score\"]}'
print('✓ Metaculus chunks immune to decay')
"

# 4. Start Streamlit and verify it loads
streamlit run app/main.py --server.headless true &
sleep 4
curl -s http://localhost:8501 | grep -q "streamlit" && echo "✓ Streamlit running"
kill %1
```

---

## Acceptance Criteria

1. **Seed Pipeline:** `python scripts/seed_db.py` completes without errors, produces >50 documents and >200 chunks
2. **Conflict Detection:** At least 1 entry in `quarantine_queue` after seeding
3. **Falsification:** At least 1 `"falsified_by_resolution"` conflict if overlapping topics exist between Metaculus resolutions and news articles
4. **Decay Immunity:** All chunks from `metaculus` documents have `decay_score = 1.0`
5. **Retrieval:** `search("AI progress")` returns results with all required keys in return dict
6. **Dashboard:** All 5 pages load without Python errors
7. **Idempotency:** Running `seed_db.py` twice does not duplicate documents or chunks
