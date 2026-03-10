import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone, timedelta
import sys

sys.path.insert(0, ".")
from ragops.config import get_supabase, DECAY_HALF_LIFE_DAYS
from ragops.decay import compute_decay

st.set_page_config(page_title="Decay Simulation", layout="wide")
st.title("📉 Decay Simulation")
st.markdown("Simulate how corpus health degrades over time.")

try:
    sb = get_supabase()

    # --- Simulation slider ---
    months_ahead = st.slider("Simulate X months into the future", 1, 36, 6)
    future_days = months_ahead * 30

    # Fetch all chunks + their documents
    chunks_result = sb.table("chunks").select("id, document_id, decay_score").execute()
    chunks = chunks_result.data or []

    docs_result = sb.table("documents").select("id, source_type, last_modified").execute()
    docs_by_id = {d["id"]: d for d in (docs_result.data or [])}

    if not chunks:
        st.info("No chunks found. Run `python scripts/seed_db.py` to populate the database.")
        st.stop()

    # Calculate projected decay scores
    projected = []
    now = datetime.now(timezone.utc)
    for c in chunks:
        doc = docs_by_id.get(c["document_id"], {})
        source_type = doc.get("source_type", "news_article")

        if source_type == "metaculus":
            projected_score = 1.0
        else:
            last_modified = doc.get("last_modified")
            if last_modified:
                try:
                    lm = last_modified.replace("Z", "+00:00")
                    lm_dt = datetime.fromisoformat(lm)
                    if lm_dt.tzinfo is None:
                        lm_dt = lm_dt.replace(tzinfo=timezone.utc)
                    future_dt = now + timedelta(days=future_days)
                    days_old = max(0, (future_dt - lm_dt).days)
                except Exception:
                    days_old = future_days
            else:
                days_old = future_days
            projected_score = compute_decay(days_old, DECAY_HALF_LIFE_DAYS)

        projected.append({
            "chunk_id": c["id"],
            "current_decay": c.get("decay_score") or 1.0,
            "projected_decay": projected_score,
            "source_type": source_type,
            "below_threshold": projected_score < 0.3,
        })

    df = pd.DataFrame(projected)

    # --- Summary metrics ---
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Chunks", len(df))
    col2.metric(f"Avg Projected Decay ({months_ahead}mo)", f"{df['projected_decay'].mean():.3f}")
    below = df["below_threshold"].sum()
    col3.metric("Chunks below 0.3 threshold", int(below), delta=f"-{below}" if below > 0 else None, delta_color="inverse")

    st.markdown("---")

    # --- Distribution histogram ---
    fig = px.histogram(
        df,
        x="projected_decay",
        color="source_type",
        nbins=20,
        title=f"Projected Decay Score Distribution ({months_ahead} months ahead)",
        labels={"projected_decay": "Projected Decay Score", "count": "Chunks"},
    )
    fig.add_vline(x=0.3, line_dash="dash", line_color="red", annotation_text="0.3 threshold")
    st.plotly_chart(fig, use_container_width=True)

    # --- At-risk chunks ---
    at_risk = df[df["below_threshold"]].head(20)
    if not at_risk.empty:
        st.subheader(f"⚠ Chunks projected below 0.3 threshold ({len(at_risk)} shown)")
        st.dataframe(at_risk[["chunk_id", "current_decay", "projected_decay", "source_type"]], use_container_width=True)

    st.markdown("---")

    # --- Run actual decay pass ---
    st.subheader("Apply Decay to Live Database")
    st.warning("This will update `chunks.decay_score` for all non-Metaculus chunks based on today's date.")
    if st.button("▶ Run Actual Decay Pass"):
        from scripts.run_decay import run_decay_pass
        with st.spinner("Running decay pass..."):
            run_decay_pass()
        st.success("Decay pass complete. Refresh the page to see updated scores.")

except Exception as e:
    st.error(f"Database connection error: {e}")
    st.info("Make sure your `.env` file is configured with valid Supabase credentials.")
