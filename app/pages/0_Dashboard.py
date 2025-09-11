# 0_Dashboard.py
import streamlit as st
from datetime import datetime, timedelta

from lib.auth import login_form, has_permission
from lib.sp_wrappers import kpis
from lib.db import query

st.set_page_config(page_title="Gym Manager", page_icon="🏋️", layout="wide")

# --------------------------
# Header: título + botón Salir
# --------------------------
left, right = st.columns([0.8, 0.2])
with left:
    st.title("🏋️ Gym Manager — Dashboard")
with right:
    if st.session_state.get("user"):
        if st.button("🚪 Salir", type="primary", help="Cerrar sesión"):
            try:
                from lib.auth import logout
                logout()
            except Exception:
                for k in ("user", "permissions", "jwt", "auth_user", "session_id", "col_index"):
                    st.session_state.pop(k, None)
            st.success("Sesión cerrada.")
            st.rerun()

# --------------------------
# Si no hay sesión: login
# --------------------------
if not st.session_state.get("user"):
    login_form()
    st.stop()

# --------------------------
# Usuario logueado
# --------------------------
u = st.session_state["user"]
st.success(f"Hola, {u.get('email','usuario')} ({u.get('rol','—')})")

# --------------------------
# Filtros (Sede y rango)
# --------------------------
sedes = query("SELECT id, nombre FROM sede ORDER BY nombre;")
sede_ids = [s["id"] for s in sedes]
sede_nombres = {s["id"]: s["nombre"] for s in sedes}

col_f1, col_f2 = st.columns([2,1])
with col_f1:
    sede_id = st.selectbox(
        "Sede",
        options=sede_ids,
        format_func=lambda i: sede_nombres.get(i, f"Sede {i}"),
        index=0 if sede_ids else None
    )
with col_f2:
    rango_dias = st.slider("Rango (días) para gráficos/tablas", 7, 60, 30, 1)

fecha_desde = (datetime.now() - timedelta(days=rango_dias)).date()

# --------------------------
# KPIs via SP (fallback a SQL)
# --------------------------
try:
    data = kpis() or []
    d = data[0] if data else {}
    socios = d.get("socios", "—")
    activas = d.get("membresias_activas", "—")
    accesos = d.get("accesos_hoy", "—")
except Exception:
    socios  = query("SELECT COUNT(*) c FROM socio")[0]["c"]
    activas = query("SELECT COUNT(*) c FROM membresia WHERE estado='activa' AND fecha_fin>=CURRENT_DATE")[0]["c"]
    accesos = query("SELECT COUNT(*) c FROM acceso WHERE fecha_entrada::date=CURRENT_DATE")[0]["c"]

# aforo actual por sede (usa tu SP)
try:
    aforo = query("SELECT sp_aforo_actual(:sede) AS aforo;", {"sede": int(sede_id)})[0]["aforo"]
except Exception:
    aforo = "—"

c1, c2, c3, c4 = st.columns(4)
c1.metric("👥 Socios", socios)
c2.metric("🪪 Membresías activas", activas)
c3.metric("🚪 Accesos hoy", accesos)
c4.metric(f"🏟️ Aforo actual · {sede_nombres.get(sede_id,'')}", aforo)

# --------------------------
# Atajos
# --------------------------
st.header("Atajos")

cols = st.columns(3)
if "col_index" not in st.session_state:
    st.session_state["col_index"] = 0

def add_link(path: str, label: str, icon: str):
    idx = st.session_state.get("col_index", 0)
    with cols[idx % 3]:
        st.page_link(path, label=label, icon=icon)
    st.session_state["col_index"] = idx + 1

st.session_state["col_index"] = 0  # reinicia al pintar

if has_permission("socios_read"):
    add_link("pages/1_Socios.py", "Socios", "👤")
if has_permission("membership_assign") or has_permission("plans_manage"):
    add_link("pages/2_Membresias.py", "Membresías", "💳")
if has_permission("classes_publish") or has_permission("reservations_create"):
    add_link("pages/3_Clases.py", "Clases", "📆")
if has_permission("access_entry") or has_permission("access_exit"):
    add_link("pages/4_Accesos_Aforo.py", "Accesos/Aforo", "🚪")
if has_permission("reports_view"):
    add_link("pages/5_Reportes.py", "Reportes", "📊")
if has_permission("users_manage"):
    add_link("pages/6_Usuarios.py", "Usuarios (admin)", "👥")
if has_permission("products_manage"):
    add_link("pages/7_Productos.py", "Productos", "🛒")
if has_permission("sales_read") or has_permission("sales_create"):
    add_link("pages/8_Ventas.py", "Ventas", "💵")
if has_permission("audit_view"):
    add_link("pages/9_Auditoria.py", "Auditoría", "📑")
if has_permission("payments_read") or has_permission("payments_create"):
    add_link("pages/10_Pagos.py", "Pagos", "💳")

st.divider()

# --------------------------
# Próximas clases
# --------------------------
st.subheader("📅 Próximas clases (48h)")

clases = query(
    """
    SELECT c.id, c.nombre, s.nombre AS sede, c.fecha_hora, c.capacidad,
           COALESCE((SELECT COUNT(*) FROM reserva r
                     WHERE r.clase_id=c.id AND r.estado='confirmada'),0) AS reservas
    FROM clase c
    JOIN sede s ON s.id=c.sede_id
    WHERE c.fecha_hora >= now() - interval '1 hour'
      AND c.fecha_hora <= now() + interval '48 hours'
      AND c.sede_id = :sede
    ORDER BY c.fecha_hora
    LIMIT 20
    """,
    {"sede": int(sede_id)}
)

# añade % de ocupación si hay filas
if clases:
    for row in clases:
        cap = row.get("capacidad") or 0
        res = row.get("reservas") or 0
        row["ocupacion_%"] = round(100 * res / cap, 1) if cap > 0 else 0.0

st.dataframe(clases, use_container_width=True)

# --------------------------
# Comprobación rápida de DB (puedes borrar esto luego)
# --------------------------
try:
    ping = query("SELECT 1 AS ok;")[0]["ok"]
    st.caption(f"DB ok = {ping}")
except Exception as e:
    st.error(f"DB error: {e}")
