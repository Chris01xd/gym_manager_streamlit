import streamlit as st
from app.lib.auth import require_login
from app.lib.db import query, execute
from app.lib.sp_wrappers import alta_socio
from app.lib.ui import load_base_css, badge

st.set_page_config(page_title="Socios", page_icon="👤", layout="wide")
load_base_css()
st.title("👤 Socios")

require_login()

tab_listar, tab_crear, tab_editar = st.tabs(["📋 Listar / Buscar", "➕ Crear", "✏️ Editar / Eliminar"])

with tab_listar:
    c1, c2 = st.columns([2,1])
    with c1:
        q = st.text_input("🔎 Buscar por nombre o email", "")
    with c2:
        limit = st.selectbox("Límite", [50, 100, 200, 500], index=1)

    params = ()
    sql = "SELECT id, dni, nombre, email, telefono, estado, fecha_alta FROM socio "
    if q.strip():
        sql += "WHERE nombre ILIKE %s OR email ILIKE %s "
        params = (f"%{q}%", f"%{q}%")
    sql += "ORDER BY id DESC LIMIT %s"
    params = params + (limit,)

    rows = query(sql, params)
    st.dataframe(rows, use_container_width=True)
    st.caption("Tip: usa el buscador para filtrar.")

with tab_crear:
    st.subheader("Alta de socio")
    with st.form("f_alta"):
        c1, c2 = st.columns(2)
        with c1:
            dni = st.text_input("DNI")
            nombre = st.text_input("Nombre *")
            email = st.text_input("Email")
        with c2:
            telefono = st.text_input("Teléfono")
            estado = st.selectbox("Estado", ["activo", "inactivo"], index=0)
        ok = st.form_submit_button("Crear socio")
    if ok:
        if not nombre.strip():
            st.error("Nombre es obligatorio")
        else:
            # usar SP para validar duplicados
            res = alta_socio(dni.strip() or None, nombre.strip(), email.strip() or None, telefono.strip() or None)
            r = res[0] if res else {}
            if r.get("status") == "OK":
                st.success(f"Socio creado (ID {r.get('socio_id')})")
            else:
                st.error(f"{r.get('message')} (code {r.get('code')})")

with tab_editar:
    st.subheader("Editar / Eliminar")
    socios = query("SELECT id, nombre, email FROM socio ORDER BY id DESC LIMIT 300")
    if not socios:
        st.info("No hay socios aún.")
    else:
        sel = st.selectbox("Selecciona un socio", socios, format_func=lambda x: f"{x['id']} - {x['nombre']} ({x['email'] or 's/ email'})")
        if sel:
            data = query("SELECT id, dni, nombre, email, telefono, estado FROM socio WHERE id=%s", (sel["id"],))
            s = data[0]
            with st.form("f_edit"):
                c1, c2 = st.columns(2)
                with c1:
                    dni = st.text_input("DNI", s["dni"] or "")
                    nombre = st.text_input("Nombre *", s["nombre"] or "")
                    email = st.text_input("Email", s["email"] or "")
                with c2:
                    telefono = st.text_input("Teléfono", s["telefono"] or "")
                    estado = st.selectbox("Estado", ["activo","inactivo"], index=0 if (s["estado"]=="activo") else 1)
                c3, c4, c5 = st.columns([1,1,2])
                upd = c3.form_submit_button("💾 Guardar")
                delb = c4.form_submit_button("🗑️ Eliminar", type="primary")
            if upd:
                execute(
                    "UPDATE socio SET dni=%s, nombre=%s, email=%s, telefono=%s, estado=%s WHERE id=%s",
                    (dni or None, nombre.strip(), email or None, telefono or None, estado, s["id"])
                )
                st.success("Actualizado")
                st.rerun()
            if delb:
                execute("DELETE FROM socio WHERE id=%s", (s["id"],))
                st.success("Eliminado")
                st.rerun()
