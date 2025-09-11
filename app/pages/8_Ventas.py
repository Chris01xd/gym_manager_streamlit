# app/pages/8_Ventas.py
# ──────────────────────────────────────────────────────────────────────────────
# Bootstrap robusto de imports: encuentra ROOT, ajusta sys.path
from pathlib import Path
import sys
import importlib.util

HERE = Path(__file__).resolve()

# Busca hacia arriba un directorio que contenga "app"
ROOT = None
for p in [HERE.parent, *HERE.parents]:
    if (p / "app").exists():
        ROOT = p
        break
if ROOT is None:
    # fallback a 2 niveles (/<ROOT>/app/pages/este_archivo.py)
    ROOT = HERE.parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Intento normal de import; si falla, carga por ruta (sin __init__.py)
def _load_module(modname: str, path: Path):
    spec = importlib.util.spec_from_file_location(modname, str(path))
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader, f"No se pudo crear spec para {modname}"
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod

try:
    from app.lib.auth import require_login, has_permission, require_perm
    from app.lib.db import query, db_cursor
    from app.lib.ui import load_base_css
except Exception:
    # Carga defensiva por archivo
    app_lib = ROOT / "app" / "lib"
    ui = _load_module("app.lib.ui", app_lib / "ui.py")
    db = _load_module("app.lib.db", app_lib / "db.py")
    auth = _load_module("app.lib.auth", app_lib / "auth.py")
    # Exporta símbolos como si fueran importados
    load_base_css = ui.load_base_css
    query = db.query
    db_cursor = db.db_cursor
    require_login = auth.require_login
    has_permission = auth.has_permission
    require_perm = auth.require_perm
# ──────────────────────────────────────────────────────────────────────────────

import streamlit as st
from datetime import datetime, date, time
from typing import Any, Dict, List, Optional, Iterable

# ------------------------------------------------------------------------------
# Utilidades
# ------------------------------------------------------------------------------

def _to_datetime(v: Any) -> Optional[datetime]:
    """Convierte a datetime si viene como str/date/None. Devuelve None si no puede."""
    if isinstance(v, datetime):
        return v
    if isinstance(v, date) and not isinstance(v, datetime):
        return datetime.combine(v, time.min)
    if v is None:
        return None
    s = str(v).strip().replace("Z", "")
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(s, fmt)
                if fmt == "%Y-%m-%d":
                    dt = datetime.combine(dt.date(), time.min)
                return dt
            except Exception:
                pass
    return None

def _fmt_money(v: Any) -> str:
    try:
        return f"S/ {float(v):.2f}"
    except Exception:
        return "S/ 0.00"

# ------------------------------------------------------------------------------
# Configuración de página
# ------------------------------------------------------------------------------

st.set_page_config(page_title="Ventas", page_icon="💵", layout="wide")
load_base_css()
st.title("💵 Ventas")

require_login()

# ------------------------------------------------------------------------------
# Helpers de negocio
# ------------------------------------------------------------------------------

def mostrar_recibo_streamlit(venta_data: Dict[str, Any], items_data: Iterable[Dict[str, Any]]):
    """Muestra el recibo usando SOLO componentes nativos de Streamlit."""
    try:
        fecha_dt = _to_datetime(venta_data.get("fecha"))
        fecha_formateada = fecha_dt.strftime("%d/%m/%Y %H:%M") if fecha_dt else "—"

        with st.container():
            st.markdown("---")

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.write("## 🏪 RECIBO DE VENTA")
                st.write(f"**Venta N° {venta_data.get('id','—')}**")
                st.write(f"**Fecha:** {fecha_formateada}")
                st.write(f"**Cliente:** {venta_data.get('socio','—')}")

            st.markdown("---")
            st.write("### 📋 Detalle de productos:")

            recibo_items: List[Dict[str, Any]] = []
            for item in items_data:
                recibo_items.append({
                    "Producto": item.get("nombre", "—"),
                    "Cantidad": int(item.get("cantidad", 0) or 0),
                    "P. Unitario": _fmt_money(item.get("precio_unitario", item.get("precio", 0))),
                    "Subtotal": _fmt_money(item.get("subtotal", 0)),
                })

            st.table(recibo_items)

            st.markdown("---")
            _, c, _ = st.columns([1, 1, 1])
            with c:
                st.success(f"## TOTAL: {_fmt_money(venta_data.get('total', 0))}")

            st.markdown("---")
            st.write("*¡Gracias por su compra!* 😊")
    except Exception as e:
        st.error(f"Error al mostrar recibo: {e}")

def add_item_with_stock_guard(cur, venta_id: int, it: Dict[str, Any]):
    """
    Descuenta stock e inserta el ítem SOLO si alcanza el stock (op. atómica).
    Castea a numeric para que ROUND funcione con 2 argumentos.
    """
    sql = """
    WITH upd AS (
        UPDATE producto
        SET stock = stock - %s
        WHERE id = %s AND stock >= %s
        RETURNING id
    ),
    ins AS (
        INSERT INTO venta_item (venta_id, producto_id, cantidad, precio, precio_unitario, subtotal)
        SELECT
            %s,
            %s,
            %s,
            %s::numeric(12,2),
            %s::numeric(12,2),
            ROUND((%s::numeric * %s::numeric), 2)
        FROM upd
        RETURNING id
    )
    SELECT id FROM ins;
    """
    params = (
        it["cantidad"], it["producto_id"], it["cantidad"],     # upd
        venta_id, it["producto_id"], it["cantidad"],           # ins
        it["precio"], it["precio"],                            # precio y precio_unitario
        it["precio"], it["cantidad"]                           # subtotal
    )
    cur.execute(sql, params)
    row = cur.fetchone()
    if not row:
        raise Exception(f"Stock insuficiente para '{it.get('nombre', '—')}' (id {it['producto_id']}).")

def merge_or_append_item(items: List[Dict[str, Any]], prod: Dict[str, Any], cantidad: int) -> List[Dict[str, Any]]:
    """Suma cantidades si el producto ya está en el carrito, validando no exceder stock."""
    new_items = list(items)
    idx = next((i for i, x in enumerate(new_items) if x["producto_id"] == prod["id"]), None)

    stock = int(prod.get("stock", 0) or 0)
    precio = float(prod.get("precio", 0) or 0)
    cantidad = int(cantidad)

    if idx is None:
        if cantidad > stock:
            raise ValueError(f"No hay stock suficiente. Disponible: {stock}.")
        new_items.append({
            "producto_id": prod["id"],
