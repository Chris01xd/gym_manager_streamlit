import streamlit as st
from datetime import date
from app.lib.auth import require_login
from app.lib.db import query, execute
from app.lib.sp_wrappers import crear_membresia, registrar_pago
from app.lib.ui import load_base_css, badge

st.set_page_config(page_title="Membresías", page_icon="💳", layout="wide")
load_base_css()
st.title("💳 Membresías")

require_login()

tab_planes, tab_asignar, tab_listado = st.tabs(["🗂️ Planes (CRUD)", "➕ Asignar membresía", "📋 Listado de membresías"])

# --- CRUD de Planes ---
with tab_planes:
    st.subheader("Planes")
    with st.expander("➕ Crear plan"):
        with st.form("f_plan"):
            c1, c2, c3 = st.columns(3)
            with c1:
                nombre = st.text_input("Nombre *")
            with c2:
                precio = st.number_input("Precio mensual", min_value=0.0, value=120.0, step=10.0)
            with c3:
                duracion = st.number_input("Duración (días)", min_value=1, value=30, step=1)
            congel = st.number_input("Max días de congelamiento", min_value=0, value=30, step=1)
            ok = st.form_submit_button("Crear")
        if ok and nombre.strip():
            try:
                execute(
                    "INSERT INTO membresia_plan(nombre, precio_mensual, duracion_dias, max_congelamiento) VALUES (%s,%s,%s,%s)",
                    (nombre.strip(), precio, duracion, congel)
                )
                st.success("Plan creado")
            except Exception as e:
                st.error(f"No se pudo crear: {e}")

    planes = query("SELECT id, nombre, precio_mensual, duracion_dias, max_congelamiento FROM membresia_plan ORDER BY id DESC")
    st.dataframe(planes, use_container_width=True)

    st.markdown("### ✏️ Editar / Eliminar plan")
    if planes:
        sel = st.selectbox("Plan", planes, format_func=lambda p: f"{p['id']} - {p['nombre']}")
        if sel:
            with st.form("f_plan_edit"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    nombre = st.text_input("Nombre *", sel["nombre"])
                with c2:
                    precio = st.number_input("Precio mensual", min_value=0.0, value=float(sel["precio_mensual"]), step=10.0)
                with c3:
                    duracion = st.number_input("Duración (días)", min_value=1, value=int(sel["duracion_dias"]), step=1)
                congel = st.number_input("Max congelamiento", min_value=0, value=int(sel["max_congelamiento"]), step=1)
                c4, c5 = st.columns(2)
                upd = c4.form_submit_button("💾 Guardar")
                delb = c5.form_submit_button("🗑️ Eliminar", type="primary")
            if upd:
                execute(
                    "UPDATE membresia_plan SET nombre=%s, precio_mensual=%s, duracion_dias=%s, max_congelamiento=%s WHERE id=%s",
                    (nombre.strip(), precio, duracion, congel, sel["id"])
                )
                st.success("Plan actualizado")
                st.rerun()
            if delb:
                execute("DELETE FROM membresia_plan WHERE id=%s", (sel["id"],))
                st.success("Plan eliminado")
                st.rerun()

# --- Asignación de Membresías ---
with tab_asignar:
    st.subheader("Asignar miembros a un plan")
    socios = query("SELECT id, nombre FROM socio ORDER BY id DESC LIMIT 400")
    planes = query("SELECT id, nombre, precio_mensual FROM membresia_plan ORDER BY nombre")
    if socios and planes:
        c1, c2 = st.columns(2)
        with c1:
            socio = st.selectbox("Socio", socios, format_func=lambda s: f"{s['id']} - {s['nombre']}")
        with c2:
            plan = st.selectbox("Plan", planes, format_func=lambda p: f"{p['nombre']} (S/{p['precio_mensual']})")
        f_ini = st.date_input("Fecha inicio", value=date.today())
        if st.button("Crear membresía"):
            r = crear_membresia(socio["id"], plan["id"], f_ini.isoformat())[0]
            st.success(f"Membresía ID {r.get('membresia_id')}" if r.get("status")=="OK" else r.get("message"))
    else:
        st.info("Necesitas al menos 1 socio y 1 plan.")

# --- Listado y gestión rápida ---
with tab_listado:
    st.subheader("Membresías activas")
    mem = query("""
      SELECT m.id, s.nombre AS socio, p.nombre AS plan, m.fecha_inicio, m.fecha_fin, m.estado
      FROM membresia m
      JOIN socio s ON s.id = m.socio_id
      JOIN membresia_plan p ON p.id = m.plan_id
      ORDER BY m.id DESC LIMIT 300
    """)
    st.dataframe(mem, use_container_width=True)
