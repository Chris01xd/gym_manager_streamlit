import streamlit as st
from datetime import date, timedelta
from app.lib.auth import require_perm
from app.lib.db import query
from app.lib.ui import load_base_css

st.set_page_config(page_title="Auditoría", page_icon="📑", layout="wide")
load_base_css()
st.title("📑 Auditoría")

require_perm("audit_view")

c1, c2, c3, c4 = st.columns(4)
with c1:
    desde = st.date_input("Desde", value=date.today()-timedelta(days=7))
with c2:
    hasta = st.date_input("Hasta", value=date.today())
with c3:
    actor = st.text_input("Usuario (email contiene)")
with c4:
    tabla = st.text_input("Tabla (contiene)")

limit = st.selectbox("Límite", [50, 100, 200, 500], index=1)

sql = """
SELECT id, fecha, actor, accion, tabla, detalle
FROM auditoria_v
WHERE fecha::date BETWEEN %s AND %s
"""
params = [desde, hasta]

if actor.strip():
    sql += " AND actor ILIKE %s"
    params.append(f"%{actor}%")
if tabla.strip():
    sql += " AND tabla ILIKE %s"
    params.append(f"%{tabla}%")

sql += " ORDER BY fecha DESC, id DESC LIMIT %s"
params.append(limit)

rows = query(sql, tuple(params))
st.dataframe(rows, use_container_width=True)
