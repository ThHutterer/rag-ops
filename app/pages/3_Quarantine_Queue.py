import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import sys

sys.path.insert(0, ".")
from ragops.config import get_supabase

st.set_page_config(page_title="Quarantine Queue", layout="wide")
st.title("🔒 Quarantine Queue")
st.markdown("Full history of conflict resolution.")

try:
    sb = get_supabase()

    # --- Filters ---
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        status_filter = st.selectbox("Status", ["all", "pending", "approved", "rejected"])
    with col_f2:
        days_back = st.slider("Days back", 1, 90, 30)
    with col_f3:
        reason_filter = st.selectbox("Reason", ["all", "semantic_overlap", "falsified_by_resolution"])

    cutoff = (datetime.utcnow() - timedelta(days=days_back)).isoformat() + "Z"

    query = sb.table("quarantine_queue").select("*").gte("created_at", cutoff)
    if status_filter != "all":
        query = query.eq("status", status_filter)
    if reason_filter != "all":
        query = query.eq("reason", reason_filter)

    result = query.order("created_at", desc=True).execute()
    entries = result.data or []

    if not entries:
        st.info("No quarantine entries found for the selected filters.")
        st.stop()

    # Build display table
    rows = []
    for e in entries:
        chunk_result = sb.table("chunks").select("content").eq("id", e["chunk_id"]).execute()
        preview = chunk_result.data[0]["content"][:100] + "..." if chunk_result.data else "(not found)"
        rows.append({
            "Preview": preview,
            "Reason": e.get("reason", ""),
            "Similarity": round(e.get("similarity", 0.0), 4),
            "Status": e.get("status", ""),
            "Created": e.get("created_at", "")[:10],
            "Reviewed": (e.get("reviewed_at") or "")[:10],
        })

    df = pd.DataFrame(rows)

    def color_status(val):
        if val == "approved":
            return "background-color: #d4edda"
        elif val == "rejected":
            return "background-color: #f8d7da"
        elif val == "pending":
            return "background-color: #fff3cd"
        return ""

    st.dataframe(df.style.applymap(color_status, subset=["Status"]), use_container_width=True)

    st.markdown("---")
    st.subheader("Resolution Rate Over Time")

    # Chart: approvals + rejections per day
    resolved_entries = [e for e in entries if e.get("reviewed_at")]
    if resolved_entries:
        chart_data = {}
        for e in resolved_entries:
            day = e["reviewed_at"][:10]
            if day not in chart_data:
                chart_data[day] = {"approved": 0, "rejected": 0}
            status = e.get("status", "")
            if status in chart_data[day]:
                chart_data[day][status] += 1

        chart_rows = [{"date": d, **v} for d, v in sorted(chart_data.items())]
        chart_df = pd.DataFrame(chart_rows)
        fig = px.line(chart_df, x="date", y=["approved", "rejected"],
                      title="Resolutions per Day",
                      labels={"value": "Count", "variable": "Status"})
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No resolved entries yet to chart.")

except Exception as e:
    st.error(f"Database connection error: {e}")
    st.info("Make sure your `.env` file is configured with valid Supabase credentials.")
