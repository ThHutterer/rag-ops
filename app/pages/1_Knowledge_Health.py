import streamlit as st
import pandas as pd
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")
from ragops.config import get_conn
from ragops.decay import compute_decay

st.set_page_config(page_title="Knowledge Health", layout="wide")
st.title("📊 Knowledge Health")


def normalize(raw):
    try:
        v = float(raw)
        return v / 10.0 if v > 1.0 else v
    except Exception:
        return 0.5


try:
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                dm.id,
                dm.title,
                dm.url,
                dm.authority_score,
                dm.created_at,
                COUNT(dp.id) AS chunk_count
            FROM document_metadata dm
            LEFT JOIN documents_pg dp ON dp.metadata->>'file_id' = dm.id
            GROUP BY dm.id, dm.title, dm.url, dm.authority_score, dm.created_at
            ORDER BY dm.created_at DESC NULLS LAST
        """)
        cols = [d[0] for d in cur.description]
        docs = [dict(zip(cols, row)) for row in cur.fetchall()]

        cur.execute("SELECT COUNT(*) FROM documents_pg")
        total_chunks = cur.fetchone()[0]
    conn.close()

    now = datetime.now(timezone.utc)
    rows = []
    health_scores = []

    for d in docs:
        auth = normalize(d["authority_score"])
        created_at = d["created_at"]
        days = 0
        if created_at:
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            days = max(0, (now - created_at).days)
        decay = compute_decay(days)
        health = auth * decay
        health_scores.append(health)

        rows.append({
            "Title": (d["title"] or "Unknown")[:60],
            "Authority": round(auth, 2),
            "Decay": round(decay, 3),
            "Health Score": round(health, 3),
            "Chunks": d["chunk_count"],
            "Days Old": days,
        })

    avg_health = sum(health_scores) / len(health_scores) if health_scores else 0.0

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total Documents", len(docs))
    col2.metric("Total Chunks", total_chunks)
    col3.metric("Avg Health Score", f"{avg_health:.3f}")
    col4.metric("Docs with Chunks", sum(1 for r in rows if r["Chunks"] > 0))

    st.markdown("---")

    df = pd.DataFrame(rows)

    def color_health(val):
        if val >= 0.7:
            return "background-color: #d4edda; color: #155724"
        elif val >= 0.4:
            return "background-color: #fff3cd; color: #856404"
        else:
            return "background-color: #f8d7da; color: #721c24"

    if not df.empty:
        styled = df.sort_values("Health Score", ascending=False).style.applymap(
            color_health, subset=["Health Score"]
        )
        st.dataframe(styled, use_container_width=True)
    else:
        st.info("No documents found.")

except Exception as e:
    st.error(f"Database connection error: {e}")
