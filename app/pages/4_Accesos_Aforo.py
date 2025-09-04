import streamlit as st
from app.lib.auth import require_login
from app.lib.db import query
from app.lib.sp_wrappers import registrar_acceso, registrar_salida, aforo_actual
from app.lib.ui import load_base_css

st.set_page_config(page_title="Accesos y Aforo", page_icon="🚪", layout="wide")
load_base_css()
st.title("🚪 Accesos y Aforo")

require_login()

sedes = query("SELECT id, nombre FROM sede ORDER BY id")
if not sedes:
    st.warning("Crea sedes (seed).")
    st.stop()

sede = st.selectbox("Sede", sedes, format_func=lambda x: f"{x['id']} - {x['nombre']}")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Aforo actual")
    st.metric("Personas dentro", aforo_actual(sede["id"]))
with c2:
    st.subheader("Accesos abiertos")
    abiertos = query(
        "SELECT id, socio_id, fecha_entrada FROM acceso WHERE sede_id=%s AND fecha_salida IS NULL ORDER BY id DESC LIMIT 100",
        (sede["id"],)
    )
    st.dataframe(abiertos, use_container_width=True)

st.divider()
st.subheader("➕ Registrar acceso de socio")
socios = query("SELECT id, nombre FROM socio ORDER BY id DESC LIMIT 300")
if socios:
    sc = st.selectbox("Socio", socios, format_func=lambda x: f"{x['id']} - {x['nombre']}")
    if st.button("Entrada"):
        r = registrar_acceso(sc["id"], sede["id"])[0]
        st.success(f"Acceso ID {r.get('acceso_id')}" if r.get("status")=="OK" else r.get("message"))
else:
    st.info("No hay socios registrados.")

st.subheader("Registrar salida")
if abiertos:
    sel = st.selectbox("Acceso", abiertos, format_func=lambda x: f"{x['id']} - socio {x['socio_id']} @ {x['fecha_entrada']}")
    if st.button("Salida"):
        r = registrar_salida(sel["id"])[0]
        st.success("Salida registrada" if r.get("status")=="OK" else r.get("message"))
