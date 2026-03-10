import streamlit as st

st.set_page_config(
    page_title="RAG Ops Dashboard",
    page_icon="🧠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("🧠 RAG Operations Dashboard")
st.markdown(
    """
    **Demonstrating production RAG operations:** staleness detection, conflict resolution,
    authority scoring, and knowledge decay.

    Use the sidebar to navigate between views.
    """
)

st.markdown("---")

col1, col2, col3 = st.columns(3)
with col1:
    st.info("**Knowledge Health**\nCorpus overview — chunk counts, health scores, flagged content.")
with col2:
    st.info("**Conflict Detection**\nReview and resolve semantic conflicts and falsified claims.")
with col3:
    st.info("**Search Playground**\nInteractive retrieval with tunable α/β/γ weights.")

st.markdown("---")
st.caption("Data: Metaculus resolved questions + RSS tech news feeds")
