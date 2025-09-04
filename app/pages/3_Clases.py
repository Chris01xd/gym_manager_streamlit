import streamlit as st
from datetime import datetime, time as dtime
from app.lib.auth import require_login
from app.lib.db import query, execute
from app.lib.sp_wrappers import publicar_clase, reservar_clase, checkin_clase
from app.lib.ui import load_base_css, badge

st.set_page_config(page_title="Clases", page_icon="📆", layout="wide")
load_base_css()
st.title("📆 Clases y Reservas")

require_login()

tab_publicar, tab_listar, tab_reservas = st.tabs(["➕ Publicar", "🗂️ Listar / Editar", "📝 Reservas / Check-in"])

with tab_publicar:
    st.subheader("Crear nueva clase")
    sedes = query("SELECT id, nombre FROM sede ORDER BY id")
    if not sedes:
        st.warning("Crea sedes primero (seed).")
    else:
        sede = st.selectbox("Sede", sedes, format_func=lambda x: f"{x['id']} - {x['nombre']}")
        nombre = st.text_input("Nombre clase", "Funcional")
        fecha = st.date_input("Fecha")
        hora = st.time_input("Hora", value=dtime(9,0))
        cap  = st.number_input("Capacidad", min_value=1, value=10)
        if st.button("Crear clase"):
            dt = datetime.combine(fecha, hora).isoformat()
            r = publicar_clase(sede["id"], nombre, dt, cap)[0]
            st.success(f"{r.get('message')} (ID {r.get('clase_id')})" if r.get("status")=="OK" else r.get("message"))

with tab_listar:
    st.subheader("Clases próximas")
    q = st.text_input("Buscar por nombre de clase")
    params = ()
    sql = """
      SELECT c.id, c.nombre, s.nombre AS sede, c.fecha_hora, c.capacidad, c.estado
      FROM clase c JOIN sede s ON s.id=c.sede_id
    """
    if q.strip():
        sql += "WHERE c.nombre ILIKE %s "
        params = (f"%{q}%",)
    sql += "ORDER BY c.fecha_hora DESC LIMIT 300"
    cl = query(sql, params)
    st.dataframe(cl, use_container_width=True)

    if cl:
        sel = st.selectbox("Selecciona una clase para editar/eliminar", cl, format_func=lambda x: f"{x['id']} - {x['nombre']} @ {x['fecha_hora']}")
        if sel:
            with st.form("f_edit_class"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    nombre = st.text_input("Nombre", sel["nombre"])
                with c2:
                    cap = st.number_input("Capacidad", min_value=1, value=int(sel["capacidad"]))
                with c3:
                    estado = st.selectbox("Estado", ["programada","cancelada","realizada"], index=["programada","cancelada","realizada"].index(sel["estado"]))
                c4, c5 = st.columns(2)
                upd = c4.form_submit_button("💾 Guardar")
                delb = c5.form_submit_button("🗑️ Eliminar", type="primary")
            if upd:
                execute("UPDATE clase SET nombre=%s, capacidad=%s, estado=%s WHERE id=%s", (nombre, cap, estado, sel["id"]))
                st.success("Clase actualizada")
                st.rerun()
            if delb:
                execute("DELETE FROM clase WHERE id=%s", (sel["id"],))
                st.success("Clase eliminada")
                st.rerun()

with tab_reservas:
    st.subheader("Reservar / Check-in")
    clases = query("SELECT id, nombre, fecha_hora FROM clase WHERE estado='programada' ORDER BY fecha_hora DESC LIMIT 200")
    socios = query("SELECT id, nombre FROM socio ORDER BY id DESC LIMIT 300")
    if clases and socios:
        c1, c2 = st.columns(2)
        with c1:
            cl = st.selectbox("Clase", clases, format_func=lambda x: f"{x['id']} - {x['nombre']} @ {x['fecha_hora']}")
        with c2:
            sc = st.selectbox("Socio", socios, format_func=lambda x: f"{x['id']} - {x['nombre']}")
        if st.button("Reservar clase"):
            r = reservar_clase(sc["id"], cl["id"])[0]
            st.success(f"Reserva ID {r.get('reserva_id')}" if r.get("status")=="OK" else r.get("message"))
    else:
        st.info("Se necesitan clases programadas y socios.")

    st.divider()
    st.subheader("Pendientes de asistencia")
    resv = query("""
      SELECT r.id, r.clase_id, r.socio_id, r.estado, c.nombre as clase
      FROM reserva r JOIN clase c ON c.id=r.clase_id
      WHERE r.estado='confirmada'
      ORDER BY r.id DESC LIMIT 200
    """)
    if resv:
        sel = st.selectbox("Reserva", resv, format_func=lambda x: f"Res {x['id']} ({x['clase']}, socio {x['socio_id']})")
        if st.button("Marcar asistencia"):
            r = checkin_clase(sel["id"])[0]
            st.success("Asistencia registrada" if r.get("status")=="OK" else r.get("message"))
    else:
        st.info("No hay reservas confirmadas recientes.")
