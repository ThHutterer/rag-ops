import streamlit as st
import sys

sys.path.insert(0, ".")
from ragops.retrieval import search

st.set_page_config(page_title="Search Playground", layout="wide")
st.title("🔍 Search Playground")
st.markdown("Interactive retrieval with tunable α/β/γ scoring weights.")

query = st.text_input("Query", placeholder="e.g. 'Wie richte ich einen neuen Benutzer ein?'")

st.markdown("**Scoring Weights**")
w1, w2, w3 = st.columns(3)
alpha = w1.slider("α — Semantic similarity", 0.0, 1.0, 0.6, 0.05)
beta = w2.slider("β — Recency / Decay", 0.0, 1.0, 0.2, 0.05)
gamma = w3.slider("γ — Authority × Decay", 0.0, 1.0, 0.2, 0.05)
st.caption(f"Score = {alpha}·semantic + {beta}·recency + {gamma}·(authority×decay)")

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
    st.warning("No results found.")
    st.stop()

st.markdown(f"**{len(results)} results** for: *{query}*")
st.markdown("---")

for i, r in enumerate(results):
    source_label = "✅ KI Text" if r["source_type"] == "ki_text" else "⚠️ Bad KI Text"
    with st.expander(
        f"#{i+1} {r['document_title'][:60]} — Score: {r['combined_score']:.4f} | {source_label}",
        expanded=i == 0,
    ):
        st.markdown(f"> {r['content'][:400]}{'...' if len(r['content']) > 400 else ''}")

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Combined", f"{r['combined_score']:.4f}")
        c2.metric("Semantic", f"{r['semantic_score']:.4f}")
        c3.metric("Recency", f"{r['recency_score']:.4f}")
        c4.metric("Auth×Decay", f"{r['authority_decay_score']:.4f}")

        m1, m2, m3 = st.columns(3)
        m1.markdown(f"**Authority:** {r['authority_score']:.2f}")
        m2.markdown(f"**Decay:** {r['decay_score']:.3f}")
        if r.get("url"):
            m3.markdown(f"[Open Document]({r['url']})")
