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
    "**Production RAG operations:** authority scoring, knowledge decay, and weighted retrieval — "
    "powered by your local knowledge base."
)
st.markdown("---")

try:
    from ragops.config import get_conn
    from ragops.decay import compute_decay
    from datetime import datetime, timezone

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents_pg")
        total_chunks = cur.fetchone()[0]

        cur.execute("SELECT COUNT(*) FROM document_metadata")
        total_docs = cur.fetchone()[0]

        cur.execute("SELECT authority_score, created_at FROM document_metadata WHERE authority_score IS NOT NULL")
        rows = cur.fetchall()
    conn.close()

    def normalize(raw):
        try:
            v = float(raw)
            return v / 10.0 if v > 1.0 else v
        except Exception:
            return 0.5

    now = datetime.now(timezone.utc)
    health_scores = []
    for raw_auth, created_at in rows:
        auth = normalize(raw_auth)
        days = 0
        if created_at:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            days = max(0, (now - created_at).days)
        health_scores.append(auth * compute_decay(days))

    avg_health = sum(health_scores) / len(health_scores) if health_scores else 0.0
    avg_auth = sum(normalize(r[0]) for r in rows) / len(rows) if rows else 0.0

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Documents", total_docs)
    c2.metric("Chunks", total_chunks)
    c3.metric("Avg Health Score", f"{avg_health:.3f}")
    c4.metric("Avg Authority", f"{avg_auth:.2f}")

except Exception as e:
    st.warning(f"Could not load live metrics: {e}")

st.markdown("---")

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**📊 Knowledge Health**\nCorpus overview — document stats, authority & health scores.")
with col2:
    st.info("**📉 Decay Simulation**\nSimulate how corpus health degrades over time.")
with col3:
    st.info("**🔍 Search Playground**\nInteractive retrieval with tunable α/β/γ weights.")
