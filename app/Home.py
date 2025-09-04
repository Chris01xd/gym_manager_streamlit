import streamlit as st, os
from app.lib.auth import login_form, has_permission
from app.lib.sp_wrappers import kpis
from app.lib.db import query

st.set_page_config(page_title="Gym Manager", page_icon="🏋️", layout="wide")

# Header: título + botón Salir
# Header: título + botón Salir con icono
left, right = st.columns([0.8, 0.2])
with left:
    st.title("🏋️ Gym Manager — Dashboard")
with right:
    if st.session_state.get("user"):
        # 🚪 icono de salida (tooltip incluido)
        if st.button("🚪 Salir", type="primary", help="Cerrar sesión"):
            try:
                from app.lib.auth import logout
                logout()
            except Exception:
                for k in ("user", "permissions", "jwt", "auth_user", "session_id", "col_index"):
                    st.session_state.pop(k, None)
            st.success("Sesión cerrada.")
            st.experimental_rerun()


# Si no hay sesión: muestra login
if not st.session_state.get("user"):
    login_form()
else:
    # Usuario logueado
    u = st.session_state["user"]
    st.success(f"Hola, {u['email']} ({u['rol']})")

    # KPIs via SP (si existe); fallback a consultas directas
    try:
        data = kpis()
        d = data[0] if data else {}
        socios = d.get("socios", "—")
        activas = d.get("membresias_activas", "—")
        accesos = d.get("accesos_hoy", "—")
    except Exception:
        socios = query("SELECT COUNT(*) c FROM socio")[0]["c"]
        activas = query("SELECT COUNT(*) c FROM membresia WHERE estado='activa' AND fecha_fin>=CURRENT_DATE")[0]["c"]
        accesos = query("SELECT COUNT(*) c FROM acceso WHERE fecha_entrada::date=CURRENT_DATE")[0]["c"]

    c1, c2, c3 = st.columns(3)
    c1.metric("Socios", socios)
    c2.metric("Membresías activas", activas)
    c3.metric("Accesos hoy", accesos)

    st.header("Atajos")

    # columnas para los botones
    cols = st.columns(3)

    def add_link(path, label, icon):
        """Agrega un link en la columna que toque"""
        nonlocal_index = st.session_state.get("col_index", 0)
        with cols[nonlocal_index % 3]:
            st.page_link(path, label=label, icon=icon)
        st.session_state["col_index"] = nonlocal_index + 1

    # reset contador al entrar
    st.session_state["col_index"] = 0

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
    st.subheader("Próximas clases (48h)")
    clases = query("""
      SELECT c.id, c.nombre, s.nombre AS sede, c.fecha_hora, c.capacidad
      FROM clase c JOIN sede s ON s.id=c.sede_id
      WHERE c.fecha_hora >= now() - interval '1 hour'
        AND c.fecha_hora <= now() + interval '48 hours'
      ORDER BY c.fecha_hora
      LIMIT 20
    """)
    st.dataframe(clases, use_container_width=True)
