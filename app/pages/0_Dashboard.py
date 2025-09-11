# 0_Dashboard.py
import os
import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

# -----------------------------
# Conexión a PostgreSQL
# -----------------------------
def get_engine():
    # Usa tus variables de entorno o ajusta aquí tus credenciales
    PG_HOST = os.getenv("PGHOST", "localhost")
    PG_PORT = os.getenv("PGPORT", "5432")
    PG_DB   = os.getenv("PGDATABASE", "gymdb")
    PG_USER = os.getenv("PGUSER", "postgres")
    PG_PASS = os.getenv("PGPASSWORD", "postgres")
    url = f"postgresql+psycopg2://{PG_USER}:{PG_PASS}@{PG_HOST}:{PG_PORT}/{PG_DB}"
    return create_engine(url, pool_pre_ping=True)

engine = get_engine()
st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
st.title("📊 Dashboard del Gimnasio")

# -----------------------------
# Filtros
# -----------------------------
with engine.connect() as conn:
    sedes = pd.read_sql("SELECT id, nombre FROM sede ORDER BY nombre;", conn)

col_f1, col_f2 = st.columns([2,1])
with col_f1:
    sede_id = st.selectbox(
        "Sede", 
        options=sedes["id"].tolist(),
        format_func=lambda i: sedes.loc[sedes["id"]==i, "nombre"].values[0],
        index=0 if not sedes.empty else None
    )
with col_f2:
    rango_dias = st.slider("Rango (días) para gráficos", min_value=7, max_value=60, value=30, step=1)

fecha_desde = (datetime.now() - timedelta(days=rango_dias)).date()

# -----------------------------
# KPIs principales (SP ya definidos)
# -----------------------------
with engine.connect() as conn:
    kpis = conn.execute(text("SELECT * FROM sp_kpis();")).mappings().first()
    aforo = conn.execute(text("SELECT sp_aforo_actual(:sede) as aforo;"), {"sede": int(sede_id)}).scalar_one()

col1, col2, col3, col4 = st.columns(4)
col1.metric("👥 Socios totales", f"{kpis['socios']:,}")
col2.metric("🪪 Membresías activas", f"{kpis['membresias_activas']:,}")
col3.metric("🚪 Accesos hoy", f"{kpis['accesos_hoy']:,}")
col4.metric(f"🏟️ Aforo actual · {sedes.loc[sedes['id']==sede_id,'nombre'].values[0]}", f"{aforo:,}")

st.divider()

# -----------------------------
# Ventas & Pagos (últimos N días)
# -----------------------------
sql_ventas = """
SELECT date_trunc('day', fecha)::date AS dia, SUM(total)::numeric(12,2) AS total
FROM venta
WHERE fecha >= :desde
GROUP BY 1 ORDER BY 1;
"""

sql_pagos = """
SELECT date_trunc('day', fecha)::date AS dia, SUM(monto)::numeric(12,2) AS total
FROM pago
WHERE fecha >= :desde
GROUP BY 1 ORDER BY 1;
"""

with engine.connect() as conn:
    df_ventas = pd.read_sql(text(sql_ventas), conn, params={"desde": fecha_desde})
    df_pagos  = pd.read_sql(text(sql_pagos),  conn, params={"desde": fecha_desde})

c1, c2 = st.columns(2)
with c1:
    st.subheader("💵 Ventas por día")
    if df_ventas.empty:
        st.info("Sin ventas en el rango seleccionado.")
    else:
        st.line_chart(df_ventas.set_index("dia")["total"])
        st.caption(f"Total: S/ {df_ventas['total'].sum():,.2f}")

with c2:
    st.subheader("💳 Pagos por día")
    if df_pagos.empty:
        st.info("Sin pagos en el rango seleccionado.")
    else:
        st.line_chart(df_pagos.set_index("dia")["total"])
        st.caption(f"Total: S/ {df_pagos['total'].sum():,.2f}")

st.divider()

# -----------------------------
# Membresías activas por plan y por vencer
# -----------------------------
sql_memb_por_plan = """
SELECT mp.nombre AS plan, COUNT(*) AS activas
FROM membresia m
JOIN membresia_plan mp ON mp.id = m.plan_id
WHERE m.estado='activa' AND m.fecha_fin >= CURRENT_DATE
GROUP BY mp.nombre
ORDER BY 2 DESC;
"""

sql_por_vencer = """
SELECT s.id AS socio_id, s.nombre, mp.nombre AS plan, m.fecha_fin
FROM membresia m
JOIN socio s ON s.id = m.socio_id
JOIN membresia_plan mp ON mp.id = m.plan_id
WHERE m.estado='activa'
  AND m.fecha_fin BETWEEN CURRENT_DATE AND CURRENT_DATE + INTERVAL '7 days'
ORDER BY m.fecha_fin;
"""

with engine.connect() as conn:
    df_plan = pd.read_sql(sql_memb_por_plan, conn)
    df_vencer = pd.read_sql(sql_por_vencer, conn)

c3, c4 = st.columns(2)
with c3:
    st.subheader("🪪 Membresías activas por plan")
    if df_plan.empty:
        st.info("No hay membresías activas.")
    else:
        st.bar_chart(df_plan.set_index("plan")["activas"])

with c4:
    st.subheader("⏳ Por vencer (próx. 7 días)")
    st.dataframe(df_vencer, use_container_width=True, hide_index=True)

st.divider()

# -----------------------------
# Clases próximas y ocupación
# -----------------------------
sql_clases = """
SELECT c.id, c.nombre, c.fecha_hora AT TIME ZONE 'UTC' AS fecha_hora_utc, c.capacidad,
       COALESCE( (SELECT COUNT(*) FROM reserva r WHERE r.clase_id=c.id AND r.estado='confirmada'), 0) AS reservas
FROM clase c
WHERE c.sede_id = :sede
  AND c.fecha_hora >= now()
ORDER BY c.fecha_hora
LIMIT 12;
"""
with engine.connect() as conn:
    df_clases = pd.read_sql(text(sql_clases), conn, params={"sede": int(sede_id)})

st.subheader("📅 Próximas clases (ocupación)")
if df_clases.empty:
    st.info("No hay clases próximas programadas.")
else:
    df_tmp = df_clases.copy()
    df_tmp["ocupación_%"] = (100 * df_tmp["reservas"] / df_tmp["capacidad"]).round(1)
    df_tmp.rename(columns={"fecha_hora_utc":"fecha_hora"}, inplace=True)
    st.dataframe(df_tmp[["id","nombre","fecha_hora","capacidad","reservas","ocupación_%"]],
                 use_container_width=True, hide_index=True)

st.divider()

# -----------------------------
# Top productos vendidos (últimos N días)
# -----------------------------
sql_top_prod = """
SELECT p.nombre, SUM(vi.cantidad) AS uds, SUM(vi.subtotal)::numeric(12,2) AS total
FROM venta_item vi
JOIN venta v ON v.id = vi.venta_id
JOIN producto p ON p.id = vi.producto_id
WHERE v.fecha >= :desde
GROUP BY p.nombre
ORDER BY total DESC
LIMIT 10;
"""
with engine.connect() as conn:
    df_prod = pd.read_sql(text(sql_top_prod), conn, params={"desde": fecha_desde})

c5, c6 = st.columns([1,1])
with c5:
    st.subheader("🏷️ Top productos (S/)")
    if df_prod.empty:
        st.info("Sin ventas de productos en el rango.")
    else:
        st.bar_chart(df_prod.set_index("nombre")["total"])
with c6:
    st.subheader("📦 Top productos (unidades)")
    if df_prod.empty:
        st.info("Sin ventas de productos en el rango.")
    else:
        st.bar_chart(df_prod.set_index("nombre")["uds"])

st.divider()

# -----------------------------
# Últimos movimientos (auditoría)
# -----------------------------
sql_audit = """
SELECT fecha, actor, accion, tabla, entidad_id, detalle
FROM auditoria_v
ORDER BY fecha DESC
LIMIT 15;
"""
with engine.connect() as conn:
    df_audit = pd.read_sql(sql_audit, conn)

st.subheader("📝 Últimos movimientos")
st.dataframe(df_audit, use_container_width=True, hide_index=True)
