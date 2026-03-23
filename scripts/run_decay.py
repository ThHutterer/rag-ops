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
from ragops.authority import NO_DECAY_SOURCE_TYPES


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

    # Fetch all decayable documents (exclude no-decay source types)
    docs = sb.table("documents").select("id, source_type, last_modified").execute()
    docs_data = [d for d in (docs.data or []) if d["source_type"] not in NO_DECAY_SOURCE_TYPES]
    print(f"Found {len(docs_data)} decayable documents")

    updated = 0
    for doc in docs_data:
        days_old = _days_since(doc["last_modified"])
        new_decay = compute_decay(days_old, DECAY_HALF_LIFE_DAYS)

        # Update all chunks for this document
        result = sb.table("chunks").update({"decay_score": new_decay}).eq("document_id", doc["id"]).execute()
        updated += len(result.data or [])

    # Ensure no-decay source types stay locked at 1.0
    all_docs = sb.table("documents").select("id, source_type").execute()
    for doc in (all_docs.data or []):
        if doc["source_type"] in NO_DECAY_SOURCE_TYPES:
            sb.table("chunks").update({"decay_score": 1.0}).eq("document_id", doc["id"]).execute()

    print(f"Decay pass complete. Updated {updated} chunks.")


if __name__ == "__main__":
    run_decay_pass()
