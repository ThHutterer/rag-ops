import streamlit as st
from datetime import datetime, timezone
import sys

sys.path.insert(0, ".")
from ragops.config import get_supabase
from ragops.retrieval import search

st.set_page_config(page_title="Search Playground", layout="wide")
st.title("🔍 Search Playground")
st.markdown("Interactive retrieval with tunable α/β/γ scoring weights.")

# --- Query input ---
query = st.text_input("Query", placeholder="e.g. 'Will AI surpass human performance on coding benchmarks?'")

# --- Weight sliders ---
st.markdown("**Scoring Weights** (α + β + γ need not sum to 1)")
w_col1, w_col2, w_col3 = st.columns(3)
alpha = w_col1.slider("α — Semantic similarity", 0.0, 1.0, 0.6, 0.05)
beta = w_col2.slider("β — Recency", 0.0, 1.0, 0.2, 0.05)
gamma = w_col3.slider("γ — Authority × Decay", 0.0, 1.0, 0.2, 0.05)

st.caption(f"Combined score = {alpha}·semantic + {beta}·recency + {gamma}·(authority×decay)")

if not query:
    st.info("Enter a query above to search the knowledge base.")
    st.stop()

with st.spinner("Searching..."):
    try:
        results = search(query, alpha=alpha, beta=beta, gamma=gamma, top_k=5)
    except Exception as e:
        st.error(f"Search error: {e}")
        st.stop()

if not results:
    st.warning("No results found. The database may be empty — run `python scripts/seed_db.py` first.")
    st.stop()

st.markdown(f"**{len(results)} results** for: *{query}*")
st.markdown("---")

sb = get_supabase()

for i, r in enumerate(results):
    badge = "🔴 Flagged" if r["flagged"] else ""
    source_emoji = {"metaculus": "🎯", "news_article": "📰", "arxiv_paper": "📄"}.get(r["source_type"], "📄")

    with st.expander(
        f"#{i+1} {source_emoji} {r['document_title'][:60]} — Score: {r['combined_score']:.4f} {badge}",
        expanded=i == 0,
    ):
        # Content preview
        st.markdown(f"> {r['content'][:300]}{'...' if len(r['content']) > 300 else ''}")

        # Score breakdown
        score_col1, score_col2, score_col3, score_col4 = st.columns(4)
        score_col1.metric("Combined", f"{r['combined_score']:.4f}")
        score_col2.metric("Semantic", f"{r['semantic_score']:.4f}")
        score_col3.metric("Recency", f"{r['recency_score']:.4f}")
        score_col4.metric("Auth×Decay", f"{r['authority_decay_score']:.4f}")

        # Metadata
        meta_col1, meta_col2, meta_col3, meta_col4 = st.columns(4)
        meta_col1.markdown(f"**Source:** `{r['source_type']}`")
        meta_col2.markdown(f"**Authority:** {r['authority_score']:.3f}")
        meta_col3.markdown(f"**Decay:** {r['decay_score']:.3f}")
        meta_col4.markdown(f"**Retrieved:** {r['retrieval_count']}×")

        # Flag chunk
        if not r["flagged"]:
            flag_key = f"flag_{r['chunk_id']}"
            if st.button("🚩 Flag this chunk", key=flag_key):
                reason = st.text_input(
                    "Flag reason",
                    key=f"reason_{r['chunk_id']}",
                    placeholder="Why is this chunk problematic?",
                )
                if reason:
                    try:
                        sb.table("chunks").update({
                            "flagged": True,
                            "flag_reason": reason,
                        }).eq("id", r["chunk_id"]).execute()
                        st.success("Chunk flagged.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error flagging chunk: {e}")
        else:
            st.warning("⚠ This chunk is flagged.")
