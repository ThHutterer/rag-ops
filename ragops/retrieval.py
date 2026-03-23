import sys
from datetime import datetime, timezone
from typing import List

sys.path.insert(0, ".")
from ragops.config import get_conn, DECAY_HALF_LIFE_DAYS
from ragops.embedder import embed
from ragops.decay import compute_decay


def _normalize_authority(raw) -> float:
    try:
        val = float(raw)
        return val / 10.0 if val > 1.0 else val
    except Exception:
        return 0.5


def _days_since(dt) -> int:
    if not dt:
        return 0
    try:
        if isinstance(dt, str):
            dt = dt.replace("Z", "+00:00")
            dt = datetime.fromisoformat(dt)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - dt).days)
    except Exception:
        return 0


def search(
    query: str,
    alpha: float = 0.6,
    beta: float = 0.2,
    gamma: float = 0.2,
    top_k: int = 5,
) -> List[dict]:
    """
    Combined scoring: score = alpha*semantic + beta*recency + gamma*(authority*decay)
    Uses documents_pg (vector store) joined with document_metadata (authority scores).
    """
    query_embedding = embed(query)
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    dp.id,
                    dp.text,
                    dp.metadata,
                    dm.title,
                    dm.url,
                    dm.authority_score,
                    dm.created_at,
                    1 - (dp.embedding <=> %s::vector) AS similarity
                FROM documents_pg dp
                LEFT JOIN document_metadata dm ON dm.id = dp.metadata->>'file_id'
                ORDER BY similarity DESC
                LIMIT %s
            """, (embedding_str, top_k * 3))

            cols = [d[0] for d in cur.description]
            raw_results = [dict(zip(cols, row)) for row in cur.fetchall()]
    finally:
        conn.close()

    scored = []
    for r in raw_results:
        authority_score = _normalize_authority(r.get("authority_score"))
        semantic_score = float(r.get("similarity") or 0.0)
        days_old = _days_since(r.get("created_at"))
        decay_score = compute_decay(days_old, DECAY_HALF_LIFE_DAYS)
        recency_score = decay_score
        authority_decay_score = authority_score * decay_score

        combined_score = (
            alpha * semantic_score
            + beta * recency_score
            + gamma * authority_decay_score
        )

        metadata = r.get("metadata") or {}
        title = r.get("title") or metadata.get("file_title", "Unknown")

        scored.append({
            "chunk_id": str(r["id"]),
            "content": r.get("text", ""),
            "combined_score": round(combined_score, 4),
            "semantic_score": round(semantic_score, 4),
            "recency_score": round(recency_score, 4),
            "authority_decay_score": round(authority_decay_score, 4),
            "source_type": "ki_text" if authority_score >= 0.8 else "bad_ki_text",
            "document_title": title,
            "authority_score": round(authority_score, 3),
            "decay_score": round(decay_score, 3),
            "flagged": False,
            "retrieval_count": 0,
            "url": r.get("url") or metadata.get("file_url", ""),
        })

    scored.sort(key=lambda x: x["combined_score"], reverse=True)
    return scored[:top_k]
