import sys
from datetime import datetime, timezone
from typing import List

sys.path.insert(0, ".")
from ragops.config import get_supabase
from ragops.embedder import embed
from ragops.decay import compute_decay


def _days_since(dt_str) -> int:
    if not dt_str:
        return 0
    try:
        if isinstance(dt_str, str):
            dt_str = dt_str.replace("Z", "+00:00")
            dt = datetime.fromisoformat(dt_str)
        else:
            dt = dt_str
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return max(0, (now - dt).days)
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
    Combined scoring search.
    score = alpha * semantic_similarity + beta * recency + gamma * (authority * decay)

    Returns list of dicts with keys:
    chunk_id, content, combined_score, semantic_score, recency_score,
    authority_decay_score, source_type, document_title, authority_score,
    decay_score, flagged, retrieval_count
    """
    sb = get_supabase()
    query_embedding = embed(query)

    # Use pgvector similarity search via RPC
    try:
        result = sb.rpc("search_chunks", {
            "query_embedding": query_embedding,
            "match_count": top_k * 3,  # fetch extra to re-rank
        }).execute()
        raw_results = result.data or []
    except Exception as e:
        print(f"Search RPC error: {e}")
        return []

    if not raw_results:
        return []

    # Fetch document metadata for each result
    doc_ids = list({r["document_id"] for r in raw_results})
    docs_result = sb.table("documents").select(
        "id, title, source_type, authority_score, last_modified"
    ).in_("id", doc_ids).execute()
    docs_by_id = {d["id"]: d for d in (docs_result.data or [])}

    now = datetime.now(timezone.utc)

    scored = []
    for r in raw_results:
        doc = docs_by_id.get(r["document_id"], {})
        source_type = doc.get("source_type", "news_article")
        authority_score = doc.get("authority_score", 0.5) or 0.5

        # Semantic score (cosine similarity from pgvector, already 0-1)
        semantic_score = float(r.get("similarity", 0.0))

        # Recency score: exponential decay based on document age (recency = decay)
        days_old = _days_since(doc.get("last_modified"))
        recency_score = compute_decay(days_old) if source_type != "metaculus" else 1.0

        # Authority * decay score
        chunk_decay = float(r.get("decay_score", 1.0))
        authority_decay_score = authority_score * chunk_decay

        # Combined score
        combined_score = (
            alpha * semantic_score
            + beta * recency_score
            + gamma * authority_decay_score
        )

        scored.append({
            "chunk_id": r["id"],
            "content": r["content"],
            "combined_score": round(combined_score, 4),
            "semantic_score": round(semantic_score, 4),
            "recency_score": round(recency_score, 4),
            "authority_decay_score": round(authority_decay_score, 4),
            "source_type": source_type,
            "document_title": doc.get("title", "Unknown"),
            "authority_score": authority_score,
            "decay_score": chunk_decay,
            "flagged": bool(r.get("flagged", False)),
            "retrieval_count": int(r.get("retrieval_count", 0)),
            "document_id": r["document_id"],
        })

    # Sort by combined score descending
    scored.sort(key=lambda x: x["combined_score"], reverse=True)
    top_results = scored[:top_k]

    # Increment retrieval_count for returned chunks
    chunk_ids = [r["chunk_id"] for r in top_results]
    for chunk_id in chunk_ids:
        try:
            current = sb.table("chunks").select("retrieval_count").eq("id", chunk_id).execute()
            if current.data:
                new_count = (current.data[0]["retrieval_count"] or 0) + 1
                sb.table("chunks").update({"retrieval_count": new_count}).eq("id", chunk_id).execute()
        except Exception:
            pass

    return top_results
