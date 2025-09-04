import streamlit as st
from app.lib.auth import require_perm, has_permission
from app.lib.db import query, execute
from app.lib.ui import load_base_css

st.set_page_config(page_title="Productos", page_icon="🛒", layout="wide")
load_base_css()
st.title("🛒 Productos")

require_perm("products_manage")

tab_listar, tab_crear, tab_editar = st.tabs(["📋 Listar/Buscar", "➕ Crear", "✏️ Editar/Eliminar"])

with tab_listar:
    c1, c2 = st.columns([2,1])
    with c1:
        q = st.text_input("🔎 Buscar por nombre", "")
    with c2:
        limit = st.selectbox("Límite", [50, 100, 200, 500], index=1)

    params = ()
    sql = "SELECT id, nombre, precio, stock, activo FROM producto "
    if q.strip():
        sql += "WHERE nombre ILIKE %s "
        params = (f"%{q}%",)
    sql += "ORDER BY id DESC LIMIT %s"
    params = params + (limit,)

    rows = query(sql, params)
    st.dataframe(rows, use_container_width=True)

with tab_crear:
    st.subheader("Crear producto")
    with st.form("f_prod_new"):
        c1, c2, c3 = st.columns(3)
        with c1:
            nombre = st.text_input("Nombre *")
        with c2:
            precio = st.number_input("Precio *", min_value=0.0, step=1.0, value=10.0)
        with c3:
            stock = st.number_input("Stock *", min_value=0, step=1, value=0)
        activo = st.checkbox("Activo", value=True)
        ok = st.form_submit_button("Crear")
    if ok:
        if not nombre.strip():
            st.error("Nombre es obligatorio")
        else:
            try:
                execute("INSERT INTO producto(nombre, precio, stock, activo) VALUES (%s,%s,%s,%s)",
                        (nombre.strip(), precio, stock, activo))
                st.success("Producto creado")
            except Exception as e:
                st.error(f"No se pudo crear: {e}")

with tab_editar:
    st.subheader("Editar/Eliminar")
    prods = query("SELECT id, nombre FROM producto ORDER BY id DESC LIMIT 300")
    if not prods:
        st.info("No hay productos.")
    else:
        sel = st.selectbox("Producto", prods, format_func=lambda p: f"{p['id']} - {p['nombre']}")
        p = query("SELECT id, nombre, precio, stock, activo FROM producto WHERE id=%s", (sel["id"],))[0]
        with st.form("f_prod_edit"):
            c1, c2, c3 = st.columns(3)
            with c1:
                nombre = st.text_input("Nombre *", p["nombre"])
            with c2:
                precio = st.number_input("Precio *", min_value=0.0, step=1.0, value=float(p["precio"]))
            with c3:
                stock = st.number_input("Stock *", min_value=0, step=1, value=int(p["stock"]))
            activo = st.checkbox("Activo", value=bool(p["activo"]))
            c4, c5 = st.columns(2)
            upd = c4.form_submit_button("💾 Guardar")
            delb = c5.form_submit_button("🗑️ Eliminar", type="primary")
        if upd:
            execute("UPDATE producto SET nombre=%s, precio=%s, stock=%s, activo=%s WHERE id=%s",
                    (nombre.strip(), precio, stock, activo, p["id"]))
            st.success("Producto actualizado")
            st.rerun()
        if delb:
            execute("DELETE FROM producto WHERE id=%s", (p["id"],))
            st.success("Producto eliminado")
            st.rerun()
