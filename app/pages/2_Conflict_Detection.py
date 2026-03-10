import streamlit as st
from datetime import datetime, timezone
import sys

sys.path.insert(0, ".")
from ragops.config import get_supabase

st.set_page_config(page_title="Conflict Detection", layout="wide")
st.title("⚡ Conflict Detection")
st.markdown("Review and resolve pending semantic conflicts.")

try:
    sb = get_supabase()

    queue_result = sb.table("quarantine_queue").select("*").eq("status", "pending").order("created_at", desc=True).execute()
    pending = queue_result.data or []

    if not pending:
        st.success("No pending conflicts. All clear!")
        st.stop()

    st.info(f"**{len(pending)} pending conflicts** awaiting review.")

    for entry in pending:
        entry_id = entry["id"]
        chunk_id = entry["chunk_id"]
        conflict_chunk_id = entry["conflict_chunk_id"]
        similarity = entry.get("similarity", 0.0)
        reason = entry.get("reason", "semantic_overlap")

        # Fetch chunk contents
        chunk_a_result = sb.table("chunks").select("content, document_id").eq("id", chunk_id).execute()
        chunk_b_result = sb.table("chunks").select("content, document_id").eq("id", conflict_chunk_id).execute()

        chunk_a = chunk_a_result.data[0] if chunk_a_result.data else {}
        chunk_b = chunk_b_result.data[0] if chunk_b_result.data else {}

        # Fetch document titles
        doc_a_result = sb.table("documents").select("title, source_type").eq("id", chunk_a.get("document_id", "")).execute()
        doc_b_result = sb.table("documents").select("title, source_type").eq("id", chunk_b.get("document_id", "")).execute()

        doc_a = doc_a_result.data[0] if doc_a_result.data else {"title": "Unknown", "source_type": "?"}
        doc_b = doc_b_result.data[0] if doc_b_result.data else {"title": "Unknown", "source_type": "?"}

        with st.expander(f"Conflict: {doc_a['title'][:40]} ↔ {doc_b['title'][:40]}", expanded=True):
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown(f"**Chunk A** — `{doc_a['source_type']}`")
                st.markdown(f"*{doc_a['title'][:60]}*")
                st.text_area("Content A", chunk_a.get("content", ""), height=150, key=f"a_{entry_id}", disabled=True)
            with col_b:
                st.markdown(f"**Chunk B** — `{doc_b['source_type']}`")
                st.markdown(f"*{doc_b['title'][:60]}*")
                st.text_area("Content B", chunk_b.get("content", ""), height=150, key=f"b_{entry_id}", disabled=True)

            # Metadata row
            meta_col1, meta_col2, meta_col3 = st.columns(3)
            meta_col1.metric("Similarity", f"{similarity:.4f}")
            with meta_col2:
                badge_color = "🔴" if reason == "falsified_by_resolution" else "🟡"
                st.markdown(f"**Reason:** {badge_color} `{reason}`")
            meta_col3.write("")

            # Action buttons
            btn_col1, btn_col2, _ = st.columns([1, 1, 4])
            if btn_col1.button("✅ Approve", key=f"approve_{entry_id}"):
                sb.table("quarantine_queue").update({
                    "status": "approved",
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", entry_id).execute()
                st.rerun()

            if btn_col2.button("❌ Reject", key=f"reject_{entry_id}"):
                sb.table("quarantine_queue").update({
                    "status": "rejected",
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", entry_id).execute()
                # Unflag the chunk
                sb.table("chunks").update({"flagged": False, "flag_reason": None}).eq("id", chunk_id).execute()
                st.rerun()

except Exception as e:
    st.error(f"Database connection error: {e}")
    st.info("Make sure your `.env` file is configured with valid Supabase credentials.")
