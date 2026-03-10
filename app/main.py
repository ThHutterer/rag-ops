import streamlit as st
import sys

sys.path.insert(0, ".")

st.set_page_config(
    page_title="RAG Ops Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🧠 RAG Operations Dashboard")
st.markdown(
    "**Demonstrating production RAG operations:** staleness detection, conflict resolution, "
    "authority scoring, and knowledge decay — powered by real public data sources."
)
st.markdown("---")

# Live KPIs
try:
    from ragops.config import get_supabase
    sb = get_supabase()

    docs = sb.table("documents").select("id, source_type").execute().data or []
    chunks = sb.table("chunks").select("id, decay_score, flagged").execute().data or []
    queue = sb.table("quarantine_queue").select("id, status").eq("status", "pending").execute().data or []

    total_docs = len(docs)
    total_chunks = len(chunks)
    flagged_chunks = sum(1 for c in chunks if c.get("flagged"))
    pending_conflicts = len(queue)

    decay_scores = [c["decay_score"] for c in chunks if c.get("decay_score") is not None]
    avg_decay = sum(decay_scores) / len(decay_scores) if decay_scores else 0.0

    kpi_ok = True
except Exception:
    kpi_ok = False

if kpi_ok:
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Documents", total_docs)
    c2.metric("Chunks", total_chunks)
    c3.metric("Avg Decay Score", f"{avg_decay:.2f}")
    c4.metric("Flagged Chunks", flagged_chunks)
    c5.metric("Pending Conflicts", pending_conflicts)
else:
    st.warning("Could not load live metrics. Check your .env configuration.")

st.markdown("---")

# Page cards
col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.info("**📊 Knowledge Health**\nCorpus overview — chunk counts, health scores, flagged content.")
with col2:
    st.info("**⚔️ Conflict Detection**\nReview and resolve semantic conflicts and falsified claims.")
with col3:
    st.info("**🔒 Quarantine Queue**\nFull history of conflict resolution with approve/reject workflow.")
with col4:
    st.info("**📉 Decay Simulation**\nSimulate how corpus health degrades over time.")
with col5:
    st.info("**🔍 Search Playground**\nInteractive retrieval with tunable α/β/γ weights.")

st.markdown("---")
st.caption("Data sources: Metaculus resolved questions · arXiv cs.AI · MIT Technology Review · Ars Technica · ORF News")
