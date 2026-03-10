import sys
from datetime import datetime, timezone
from typing import List

sys.path.insert(0, ".")
from ragops.config import get_supabase, CONFLICT_SIMILARITY_THRESHOLD
from ragops.embedder import embed, embed_batch
from ragops.chunker import chunk_text
from ragops.decay import compute_decay


def _days_since(dt_str) -> int:
    """Returns days since a datetime string (ISO8601)."""
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


def ingest_document(document_id: str) -> dict:
    """
    Fetches document from DB, chunks, embeds, upserts chunks.
    Runs conflict detection for each chunk.
    Returns: {"chunks_created": int, "conflicts_found": int}
    """
    sb = get_supabase()

    # Fetch document
    result = sb.table("documents").select("*").eq("id", document_id).execute()
    if not result.data:
        raise ValueError(f"Document {document_id} not found")
    doc = result.data[0]

    source_type = doc["source_type"]
    is_metaculus = source_type == "metaculus"
    days_old = _days_since(doc.get("last_modified"))
    decay_score = 1.0 if is_metaculus else compute_decay(days_old)

    # Chunk the content
    content = doc.get("content", "") or ""
    chunks = chunk_text(content)
    if not chunks:
        return {"chunks_created": 0, "conflicts_found": 0}

    # Batch embed
    embeddings = embed_batch(chunks)

    chunks_created = 0
    conflicts_found = 0

    for i, (chunk_content, embedding) in enumerate(zip(chunks, embeddings)):
        # Check for existing chunk (idempotency: document_id + chunk_index)
        existing = sb.table("chunks").select("id").eq("document_id", document_id).eq("chunk_index", i).execute()

        chunk_data = {
            "document_id": document_id,
            "content": chunk_content,
            "embedding": embedding,
            "chunk_index": i,
            "decay_score": decay_score,
            "flagged": False,
        }

        if existing.data:
            chunk_id = existing.data[0]["id"]
            sb.table("chunks").update(chunk_data).eq("id", chunk_id).execute()
        else:
            insert_result = sb.table("chunks").insert(chunk_data).execute()
            chunk_id = insert_result.data[0]["id"]
            chunks_created += 1

        # Conflict detection: find similar chunks from OTHER documents
        conflicts = _detect_conflicts(sb, chunk_id, embedding, document_id, doc, is_metaculus)
        conflicts_found += conflicts

    return {"chunks_created": chunks_created, "conflicts_found": conflicts_found}


def _detect_conflicts(sb, chunk_id: str, embedding: list, document_id: str, doc: dict, is_metaculus: bool) -> int:
    """
    Check this chunk against existing chunks from other documents.
    Uses pgvector cosine similarity via RPC.
    Returns number of conflicts added to quarantine_queue.
    """
    try:
        # Use pgvector similarity search via Supabase RPC or raw SQL
        # We'll use a direct query approach
        result = sb.rpc("find_similar_chunks", {
            "query_embedding": embedding,
            "match_threshold": CONFLICT_SIMILARITY_THRESHOLD,
            "match_count": 5,
            "exclude_document_id": document_id,
        }).execute()

        if not result.data:
            return 0

        conflicts_added = 0
        for match in result.data:
            conflict_chunk_id = match["id"]
            similarity = match.get("similarity", 0.0)

            # Determine reason
            if is_metaculus and doc.get("review_status") == "resolved":
                reason = "falsified_by_resolution"
            else:
                # Check if the conflicting chunk is from a metaculus resolved doc
                conflict_doc_result = sb.table("chunks").select("document_id").eq("id", conflict_chunk_id).execute()
                if conflict_doc_result.data:
                    conflict_doc_id = conflict_doc_result.data[0]["document_id"]
                    conflict_doc = sb.table("documents").select("source_type, review_status").eq("id", conflict_doc_id).execute()
                    if conflict_doc.data and conflict_doc.data[0]["source_type"] == "metaculus" and conflict_doc.data[0]["review_status"] == "resolved":
                        reason = "falsified_by_resolution"
                    else:
                        reason = "semantic_overlap"
                else:
                    reason = "semantic_overlap"

            # Check if this conflict pair already exists
            existing_conflict = sb.table("quarantine_queue").select("id").eq("chunk_id", chunk_id).eq("conflict_chunk_id", conflict_chunk_id).execute()
            if existing_conflict.data:
                continue

            # Also check reverse direction
            reverse_conflict = sb.table("quarantine_queue").select("id").eq("chunk_id", conflict_chunk_id).eq("conflict_chunk_id", chunk_id).execute()
            if reverse_conflict.data:
                continue

            # Flag the chunk
            sb.table("chunks").update({"flagged": True, "flag_reason": reason}).eq("id", chunk_id).execute()

            # Add to quarantine queue
            sb.table("quarantine_queue").insert({
                "chunk_id": chunk_id,
                "conflict_chunk_id": conflict_chunk_id,
                "similarity": similarity,
                "reason": reason,
                "status": "pending",
            }).execute()
            conflicts_added += 1

        return conflicts_added

    except Exception as e:
        # If the RPC doesn't exist yet, fall back gracefully
        print(f"  Conflict detection error: {e}")
        return 0
