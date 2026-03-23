import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timezone, timedelta
import sys

sys.path.insert(0, ".")
from ragops.config import get_conn, DECAY_HALF_LIFE_DAYS
from ragops.decay import compute_decay

st.set_page_config(page_title="Decay Simulation", layout="wide")
st.title("📉 Decay Simulation")
st.markdown("Simulate how corpus health degrades over time based on document age.")

months_ahead = st.slider("Simulate X months into the future", 1, 36, 6)
future_days = months_ahead * 30


def normalize(raw):
    try:
        v = float(raw)
        return v / 10.0 if v > 1.0 else v
    except Exception:
        return 0.5


try:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id, authority_score, created_at FROM document_metadata WHERE authority_score IS NOT NULL")
        cols = [d[0] for d in cur.description]
        docs = [dict(zip(cols, row)) for row in cur.fetchall()]
    conn.close()

    if not docs:
        st.info("No documents found.")
        st.stop()

    now = datetime.now(timezone.utc)
    rows = []
    for d in docs:
        auth = normalize(d["authority_score"])
        created_at = d["created_at"]
        current_days = 0
        if created_at:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            current_days = max(0, (now - created_at).days)

        current_decay = compute_decay(current_days, DECAY_HALF_LIFE_DAYS)
        projected_decay = compute_decay(current_days + future_days, DECAY_HALF_LIFE_DAYS)

        rows.append({
            "current_decay": round(current_decay, 3),
            "projected_decay": round(projected_decay, 3),
            "current_health": round(auth * current_decay, 3),
            "projected_health": round(auth * projected_decay, 3),
            "authority": round(auth, 2),
            "below_threshold": projected_decay < 0.3,
        })

    df = pd.DataFrame(rows)

    col1, col2, col3 = st.columns(3)
    col1.metric("Total Documents", len(df))
    col2.metric(f"Avg Projected Decay ({months_ahead}mo)", f"{df['projected_decay'].mean():.3f}")
    below = int(df["below_threshold"].sum())
    col3.metric("Docs below 0.3 threshold", below)

    st.markdown("---")

    fig = px.histogram(
        df,
        x="projected_decay",
        nbins=20,
        title=f"Projected Decay Distribution ({months_ahead} months ahead)",
        labels={"projected_decay": "Projected Decay Score"},
    )
    fig.add_vline(x=0.3, line_dash="dash", line_color="red", annotation_text="0.3 threshold")
    st.plotly_chart(fig, use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        fig2 = px.scatter(
            df, x="current_decay", y="projected_decay",
            title="Current vs Projected Decay",
            labels={"current_decay": "Current", "projected_decay": f"After {months_ahead}mo"},
        )
        st.plotly_chart(fig2, use_container_width=True)

    with col_b:
        fig3 = px.scatter(
            df, x="authority", y="projected_health",
            title="Authority vs Projected Health Score",
            labels={"authority": "Authority Score", "projected_health": "Projected Health"},
        )
        st.plotly_chart(fig3, use_container_width=True)

except Exception as e:
    st.error(f"Database connection error: {e}")
