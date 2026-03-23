import streamlit as st
import sys

sys.path.insert(0, ".")
from ragops.config import get_conn

st.set_page_config(page_title="Quarantine Queue", layout="wide")
st.title("🔒 Quarantine Queue")

QUERY_PENDING = """
    SELECT
        q.id,
        q.chunk_id,
        q.conflict_chunk_id,
        q.similarity,
        q.created_at,
        a.text        AS chunk_text,
        b.text        AS conflict_text,
        am.title      AS chunk_title,
        bm.title      AS conflict_title,
        am.authority_score AS chunk_authority,
        bm.authority_score AS conflict_authority
    FROM quarantine_queue q
    JOIN documents_pg a  ON a.id = q.chunk_id
    JOIN documents_pg b  ON b.id = q.conflict_chunk_id
    LEFT JOIN document_metadata am ON am.id = a.metadata->>'file_id'
    LEFT JOIN document_metadata bm ON bm.id = b.metadata->>'file_id'
    WHERE q.status = 'pending'
    ORDER BY q.similarity DESC, q.created_at DESC
"""

QUERY_UPDATE = """
    UPDATE quarantine_queue
    SET status = %s, reviewed_at = now()
    WHERE id = %s
"""

try:
    conn = get_conn()

    with conn.cursor() as cur:
        cur.execute(QUERY_PENDING)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, row)) for row in cur.fetchall()]

    if not rows:
        st.success("Keine offenen Konflikte.")
        st.stop()

    st.write(f"**{len(rows)} offene Konflikte**")

    for row in rows:
        similarity_pct = round(row["similarity"] * 100, 1)
        chunk_auth = float(row["chunk_authority"] or 0)
        conflict_auth = float(row["conflict_authority"] or 0)

        with st.expander(
            f"Similarity {similarity_pct}% — {row['chunk_title'] or 'Unbekannt'}  ↔  {row['conflict_title'] or 'Unbekannt'}",
            expanded=False
        ):
            col1, col2 = st.columns(2)

            with col1:
                st.markdown(f"**{row['chunk_title'] or 'Unbekannt'}**")
                st.caption(f"Authority Score: `{chunk_auth:.3f}`")
                st.text_area("Text", row["chunk_text"] or "", height=200, key=f"a_{row['id']}", disabled=True)

            with col2:
                st.markdown(f"**{row['conflict_title'] or 'Unbekannt'}**")
                st.caption(f"Authority Score: `{conflict_auth:.3f}`")
                st.text_area("Text", row["conflict_text"] or "", height=200, key=f"b_{row['id']}", disabled=True)

            higher = "Links" if chunk_auth >= conflict_auth else "Rechts"
            st.caption(f"Höherer Authority Score: **{higher}**")

            btn_col1, btn_col2, _ = st.columns([1, 1, 6])
            with btn_col1:
                if st.button("✅ Approve", key=f"approve_{row['id']}"):
                    with conn.cursor() as cur:
                        cur.execute(QUERY_UPDATE, ("approved", row["id"]))
                    conn.commit()
                    st.rerun()
            with btn_col2:
                if st.button("❌ Reject", key=f"reject_{row['id']}"):
                    with conn.cursor() as cur:
                        cur.execute(QUERY_UPDATE, ("rejected", row["id"]))
                    conn.commit()
                    st.rerun()

    conn.close()

except Exception as e:
    st.error(f"Datenbankfehler: {e}")
