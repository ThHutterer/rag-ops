import streamlit as st
import pandas as pd
import sys

sys.path.insert(0, ".")
from ragops.config import get_supabase

st.set_page_config(page_title="Knowledge Health", layout="wide")
st.title("📊 Knowledge Health")

try:
    sb = get_supabase()

    # --- Top-level metrics ---
    chunks_result = sb.table("chunks").select("id, decay_score, flagged, document_id").execute()
    chunks = chunks_result.data or []

    quarantine_result = sb.table("quarantine_queue").select("id, status").eq("status", "pending").execute()
    pending_quarantine = len(quarantine_result.data or [])

    total_chunks = len(chunks)
    flagged_count = sum(1 for c in chunks if c.get("flagged"))

    docs_result = sb.table("documents").select("id, authority_score").execute()
    docs = docs_result.data or []

    # Build authority lookup
    authority_by_doc = {d["id"]: (d.get("authority_score") or 0.5) for d in docs}

    # Avg health score = avg(authority_score * decay_score)
    health_scores = [
        (authority_by_doc.get(c["document_id"], 0.5)) * (c.get("decay_score") or 1.0)
        for c in chunks
    ]
    avg_health = sum(health_scores) / len(health_scores) if health_scores else 0.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Chunks", total_chunks)
    col2.metric("Avg Health Score", f"{avg_health:.3f}")
    col3.metric("Flagged Chunks", flagged_count)
    col4.metric("Pending Quarantine", pending_quarantine)

    st.markdown("---")

    # --- Per-document table ---
    all_docs_result = sb.table("documents").select(
        "id, title, source_type, authority_score"
    ).execute()
    all_docs = all_docs_result.data or []

    if not all_docs:
        st.info("No documents found. Run `python scripts/seed_db.py` to populate the database.")
        st.stop()

    # Build per-document stats from chunks
    doc_stats = {}
    for doc in all_docs:
        doc_id = doc["id"]
        doc_stats[doc_id] = {
            "title": doc["title"],
            "source_type": doc["source_type"],
            "authority_score": doc.get("authority_score") or 0.0,
            "chunk_count": 0,
            "total_decay": 0.0,
            "total_retrieval_count": 0,
            "flagged_chunk_count": 0,
        }

    for c in chunks:
        doc_id = c.get("document_id")
        if doc_id in doc_stats:
            doc_stats[doc_id]["chunk_count"] += 1
            doc_stats[doc_id]["total_decay"] += c.get("decay_score") or 1.0
            if c.get("flagged"):
                doc_stats[doc_id]["flagged_chunk_count"] += 1

    # Retrieval counts
    for c in chunks:
        doc_id = c.get("document_id")
        if doc_id in doc_stats:
            rc_result = sb.table("chunks").select("retrieval_count").eq("id", c["id"]).execute()
            # Already in chunks data — but we only fetched basic fields; skip for now

    rows = []
    for doc_id, stats in doc_stats.items():
        n = stats["chunk_count"]
        avg_decay = (stats["total_decay"] / n) if n > 0 else 1.0
        avg_health_doc = stats["authority_score"] * avg_decay
        rows.append({
            "Title": stats["title"][:60],
            "Source Type": stats["source_type"],
            "Authority": round(stats["authority_score"], 3),
            "Avg Decay": round(avg_decay, 3),
            "Health Score": round(avg_health_doc, 3),
            "Chunks": n,
            "Flagged": stats["flagged_chunk_count"],
        })

    df = pd.DataFrame(rows)

    def color_health(val):
        if val >= 0.7:
            return "background-color: #d4edda; color: #155724"
        elif val >= 0.4:
            return "background-color: #fff3cd; color: #856404"
        else:
            return "background-color: #f8d7da; color: #721c24"

    if not df.empty:
        df_sorted = df.sort_values("Health Score", ascending=False)
        styled = df_sorted.style.applymap(color_health, subset=["Health Score"])
        st.dataframe(styled, use_container_width=True)
    else:
        st.info("No document data available.")

except Exception as e:
    st.error(f"Database connection error: {e}")
    st.info("Make sure your `.env` file is configured with valid Supabase credentials.")
