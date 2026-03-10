"""
Apply a decay pass to all non-metaculus chunks in the database.
Updates chunks.decay_score based on the document's last_modified date.
Usage: python scripts/run_decay.py
"""
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")
from ragops.config import get_supabase, DECAY_HALF_LIFE_DAYS
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


def run_decay_pass():
    sb = get_supabase()
    print("Running decay pass...")

    # Fetch all non-metaculus documents with their chunks
    docs = sb.table("documents").select("id, source_type, last_modified").neq("source_type", "metaculus").execute()
    docs_data = docs.data or []
    print(f"Found {len(docs_data)} non-metaculus documents")

    updated = 0
    for doc in docs_data:
        days_old = _days_since(doc["last_modified"])
        new_decay = compute_decay(days_old, DECAY_HALF_LIFE_DAYS)

        # Update all chunks for this document
        result = sb.table("chunks").update({"decay_score": new_decay}).eq("document_id", doc["id"]).execute()
        updated += len(result.data or [])

    # Ensure metaculus chunks stay at 1.0
    meta_docs = sb.table("documents").select("id").eq("source_type", "metaculus").execute()
    for doc in (meta_docs.data or []):
        sb.table("chunks").update({"decay_score": 1.0}).eq("document_id", doc["id"]).execute()

    print(f"Decay pass complete. Updated {updated} chunks.")


if __name__ == "__main__":
    run_decay_pass()
