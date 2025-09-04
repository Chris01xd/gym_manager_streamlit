import streamlit as st, hashlib
from app.lib.auth import require_role
from app.lib.db import query, execute
from app.lib.ui import load_base_css

st.set_page_config(page_title="Usuarios", page_icon="👥", layout="wide")
load_base_css()
st.title("👥 Administración de Usuarios")
require_role("admin")

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

roles = ["admin", "recepcion", "entrenador", "finanzas"]
sedes = query("SELECT id, nombre FROM sede ORDER BY id")
sede_opts = {s["nombre"]: s["id"] for s in sedes} if sedes else {}

tab_crear, tab_listar = st.tabs(["➕ Crear", "📋 Listar / Editar / Eliminar"])

with tab_crear:
    with st.form("f_user_new"):
        c1, c2 = st.columns(2)
        with c1:
            email = st.text_input("Email *")
            password = st.text_input("Contraseña *", type="password")
        with c2:
            rol = st.selectbox("Rol *", roles, index=0)
            sede_nombre = st.selectbox("Sede", list(sede_opts.keys()) if sede_opts else ["—"])
        ok = st.form_submit_button("Crear usuario")
    if ok:
        if not email or not password:
            st.error("Email y contraseña son obligatorios")
        else:
            try:
                execute(
                    "INSERT INTO app_user(email, password_hash, rol, sede_id) VALUES (%s,%s,%s,%s)",
                    (email, sha256(password), rol, sede_opts.get(sede_nombre))
                )
                st.success("Usuario creado")
            except Exception as e:
                st.error(f"No se pudo crear: {e}")

with tab_listar:
    users = query("""
        SELECT u.id, u.email, u.rol, u.sede_id, s.nombre AS sede, u.created_at
        FROM app_user u LEFT JOIN sede s ON s.id=u.sede_id
        ORDER BY u.id DESC
    """)
    if not users:
        st.info("No hay usuarios.")
        st.stop()

    st.dataframe(users, use_container_width=True, hide_index=True)

    st.subheader("Editar / Resetear / Eliminar")
    sel = st.selectbox("Usuario", users, format_func=lambda u: f"{u['id']} - {u['email']}")
    if sel:
        with st.form("f_user_edit"):
            c1, c2, c3 = st.columns(3)
            with c1:
                rol_new = st.selectbox("Rol", roles, index=roles.index(sel["rol"]) if sel["rol"] in roles else 0)
            with c2:
                sede_new = st.selectbox("Sede", list(sede_opts.keys()) if sede_opts else ["—"], index=0)
            with c3:
                nueva_pw = st.text_input("Nueva contraseña (opcional)", type="password")
            c4, c5, c6 = st.columns(3)
            upd = c4.form_submit_button("💾 Guardar")
            delb = c5.form_submit_button("🗑️ Eliminar", type="primary")
        if upd:
            if nueva_pw:
                execute("UPDATE app_user SET password_hash=%s WHERE id=%s", (sha256(nueva_pw), sel["id"]))
            execute("UPDATE app_user SET rol=%s, sede_id=%s WHERE id=%s", (rol_new, sede_opts.get(sede_new), sel["id"]))
            st.success("Actualizado")
            st.rerun()
        if delb:
            me = st.session_state.get("user")
            if me and me["id"] == sel["id"]:
                st.error("No puedes eliminar tu propio usuario.")
            else:
                execute("DELETE FROM app_user WHERE id=%s", (sel["id"],))
                st.success("Eliminado")
                st.rerun()
