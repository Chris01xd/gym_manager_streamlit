import streamlit as st, pandas as pd, plotly.express as px
from app.lib.auth import require_login
from app.lib.db import query
from app.lib.ui import load_base_css

st.set_page_config(page_title="Reportes", page_icon="📊", layout="wide")
load_base_css()
st.title("📊 Reportes")

require_login()

st.subheader("Ingresos por día (últimos 60)")
rows = query("SELECT date(fecha) as dia, sum(monto) as ingresos FROM pago GROUP BY 1 ORDER BY 1 DESC LIMIT 60")
df = pd.DataFrame(rows)
if not df.empty:
    fig = px.line(df.sort_values("dia"), x="dia", y="ingresos", markers=True, title="Ingresos diarios")
    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(df.sort_values("dia", ascending=False), use_container_width=True)
else:
    st.info("No hay pagos registrados.")

st.subheader("Exportar socios")
socios = query("SELECT id, dni, nombre, email, telefono, estado, fecha_alta FROM socio ORDER BY id DESC")
df2 = pd.DataFrame(socios)
st.download_button("Descargar CSV", data=df2.to_csv(index=False), file_name="socios.csv", mime="text/csv")
st.dataframe(df2.head(200), use_container_width=True)
