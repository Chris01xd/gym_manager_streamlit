# app/pages/8_Ventas.py  (o 02_Ventas.py)
# ──────────────────────────────────────────────────────────────────────────────
# Bootstrap local de imports: NO toca otras vistas
from pathlib import Path
import sys, importlib.util

HERE = Path(__file__).resolve()

# Ubica el ROOT (carpeta que contiene "app")
ROOT = None
for p in [HERE.parent, *HERE.parents]:
    if (p / "app").exists():
        ROOT = p
        break
if ROOT is None:
    ROOT = HERE.parents[2]  # fallback típico: /<ROOT>/app/pages/este_archivo.py

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

def _load_module(modname: str, path: Path):
    """Carga un módulo por ruta (sirve aunque no haya __init__.py)."""
    spec = importlib.util.spec_from_file_location(modname, str(path))
    if not spec or not spec.loader:
        raise ImportError(f"No se pudo crear spec para {modname} en {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[attr-defined]
    return mod

# Intenta import normal de tus libs
try:
    from app.lib.auth import require_login, has_permission, require_perm
    from app.lib.db import query, db_cursor
    from app.lib.ui import load_base_css
except Exception:
    # Si falla, intenta carga por archivo
    app_lib = ROOT / "app" / "lib"
    # auth
    try:
        _auth = _load_module("app.lib.auth", app_lib / "auth.py")
        require_login = _auth.require_login
        has_permission = _auth.has_permission
        require_perm = _auth.require_perm
    except Exception as e:
        # Falla crítica: sin auth no seguimos
        import streamlit as st
        st.stop()  # interrumpe ejecución temprana para evitar trazas largas

    # db
    try:
        _db = _load_module("app.lib.db", app_lib / "db.py")
        query = _db.query
        db_cursor = _db.db_cursor
    except Exception:
        import streamlit as st
        st.error("No se pudo cargar app.lib.db (query/db_cursor). Revisa app/lib/db.py.")
        st.stop()

    # ui (opcional): si no existe, usamos fallback
    try:
        _ui = _load_module("app.lib.ui", app_lib / "ui.py")
        load_base_css = _ui.load_base_css
    except Exception:
        def load_base_css():
            import streamlit as st
            st.markdown(
                "<style>/* CSS base mínimo */ .stButton>button{font-weight:600}</style>",
                unsafe_allow_html=True
            )

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
    # ISOfirst
    try:
        return datetime.fromisoformat(s)
    except Exception:
        pass
    # formatos comunes
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(s, fmt)
            if fmt == "%Y-%m-%d":
                dt = datetime.combine(dt.date(), time.min)
            return dt
        except Exception:
            continue
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
            "nombre": prod.get("nombre", "—"),
            "precio": float(precio),
            "cantidad": cantidad,
            "subtotal": round(precio * cantidad, 2),
        })
    else:
        nueva_cant = int(new_items[idx]["cantidad"]) + cantidad
        if nueva_cant > stock:
            raise ValueError(
                f"No hay stock suficiente. En carrito: {new_items[idx]['cantidad']}, disponible: {stock}."
            )
        new_items[idx]["cantidad"] = nueva_cant
        new_items[idx]["subtotal"] = round(float(new_items[idx]["precio"]) * nueva_cant, 2)

    return new_items

# ------------------------------------------------------------------------------
# UI
# ------------------------------------------------------------------------------

tab_nueva, tab_listado = st.tabs(["➕ Nueva venta", "📋 Listado / Anular"])

# =========================
# ➕ NUEVA VENTA
# =========================
with tab_nueva:
    if not has_permission("sales_create"):
        st.info("No tienes permiso para crear ventas.")
    else:
        socios = query("SELECT id, nombre FROM socio ORDER BY id DESC LIMIT 300")
        prods = query("SELECT id, nombre, precio, stock FROM producto WHERE activo IS TRUE AND stock > 0 ORDER BY nombre")

        if not socios:
            st.warning("Necesitas al menos 1 socio registrado.")
        elif not prods:
            st.warning("No hay productos activos con stock disponible.")
        else:
            socio = st.selectbox(
                "Socio",
                socios,
                format_func=lambda s: f"{s['id']} - {s['nombre']}"
            )

            st.markdown("### Ítems")

            if "venta_items" not in st.session_state:
                st.session_state["venta_items"] = []

            with st.form("f_add_item", clear_on_submit=True):
                col1, col2, col3 = st.columns([3, 1, 1])

                with col1:
                    prod = st.selectbox(
                        "Producto",
                        prods,
                        format_func=lambda p: f"{p['nombre']} - S/{float(p['precio']):.2f} (Stock: {int(p['stock'])})",
                        key="prod_select"
                    )

                with col2:
                    if prod and int(prod.get("stock", 0) or 0) > 0:
                        stock_en_carrito = 0
                        for item in st.session_state["venta_items"]:
                            if item["producto_id"] == prod["id"]:
                                stock_en_carrito = int(item["cantidad"])
                                break
                        max_disponible = int(prod["stock"]) - stock_en_carrito
                        max_cant = max(1, max_disponible)
                        cant = st.number_input("Cant.", min_value=1, value=1, step=1, max_value=max_cant)
                    else:
                        cant = st.number_input("Cant.", min_value=1, value=1, step=1, disabled=True)

                with col3:
                    add = st.form_submit_button("➕ Agregar", disabled=(not prod or int(prod.get("stock", 0) or 0) <= 0))

            if add and prod:
                try:
                    st.session_state["venta_items"] = merge_or_append_item(st.session_state["venta_items"], prod, int(cant))
                    st.success(f"✅ Agregado: {prod['nombre']} x {int(cant)}")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

            items = st.session_state["venta_items"]
            if items:
                st.markdown("**Carrito actual:**")

                for i, item in enumerate(items):
                    col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                    with col1:
                        st.write(item["nombre"])
                    with col2:
                        st.write(int(item["cantidad"]))
                    with col3:
                        st.write(_fmt_money(item["precio"]))
                    with col4:
                        st.write(_fmt_money(item["subtotal"]))
                    with col5:
                        if st.button("🗑️", key=f"del_{i}", help="Eliminar item"):
                            st.session_state["venta_items"].pop(i)
                            st.rerun()

                total = round(sum(float(it.get("subtotal", 0) or 0) for it in items), 2)
                st.markdown(f"### **Total: {_fmt_money(total)}**")

                col_confirmar, col_limpiar, col_fecha = st.columns([1, 1, 2])
                with col_confirmar:
                    confirmar = st.button("💾 Confirmar venta", type="primary")
                with col_limpiar:
                    limpiar = st.button("🧹 Limpiar carrito")
                with col_fecha:
                    fecha_venta = st.date_input("Fecha de venta", value=date.today())

                if limpiar:
                    st.session_state["venta_items"] = []
                    st.success("🧹 Carrito limpiado")
                    st.rerun()

                if confirmar:
                    try:
                        with db_cursor(commit=True) as cur:
                            # Cabecera
                            cur.execute(
                                "INSERT INTO venta(socio_id, fecha, total) VALUES (%s, %s, %s) RETURNING id",
                                (socio["id"], datetime.combine(fecha_venta, datetime.now().time()), total)
                            )
                            venta_id = cur.fetchone()["id"]

                            # Ítems con validación de stock
                            for it in items:
                                add_item_with_stock_guard(cur, venta_id, it)

                            # Recalcular total
                            cur.execute("""
                                UPDATE venta v
                                SET total = COALESCE((
                                    SELECT SUM(subtotal)::numeric(12,2)
                                    FROM venta_item vi
                                    WHERE vi.venta_id = v.id
                                ), 0)
                                WHERE v.id = %s
                                RETURNING total
                            """, (venta_id,))
                            _ = cur.fetchone()["total"]

                        # Datos para recibo
                        venta_completa = query("""
                            SELECT v.id, v.fecha, v.total, s.nombre as socio
                            FROM venta v
                            JOIN socio s ON s.id = v.socio_id
                            WHERE v.id = %s
                        """, (venta_id,))[0]

                        items_recibo = query("""
                            SELECT vi.cantidad, vi.precio_unitario, vi.subtotal, p.nombre
                            FROM venta_item vi
                            JOIN producto p ON p.id = vi.producto_id
                            WHERE vi.venta_id = %s
                        """, (venta_id,))

                        st.success(f"🎉 ¡Venta registrada exitosamente! (ID: {venta_id})")
                        st.markdown("## 📄 Recibo de Venta")
                        mostrar_recibo_streamlit(venta_completa, items_recibo)

                        st.session_state["venta_items"] = []
                        if st.button("🔄 Nueva venta"):
                            st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error al registrar la venta: {str(e)}")
            else:
                st.info("📦 Agrega productos al carrito para continuar...")

                if prods:
                    st.markdown("**Productos disponibles:**")
                    top = min(5, len(prods))
                    for prod_ in prods[:top]:
                        st.write(f"• {prod_['nombre']} - {_fmt_money(prod_['precio'])} (Stock: {int(prod_['stock'])})")
                    if len(prods) > top:
                        st.write(f"... y {len(prods) - top} productos más")

# =========================
# 📋 LISTADO / ANULAR
# =========================
with tab_listado:
    require_perm("sales_read")
    st.subheader("📋 Ventas recientes")

    col_busq, col_fecha = st.columns([2, 1])
    with col_busq:
        q = st.text_input("🔍 Buscar por socio (nombre)")
    with col_fecha:
        filtro_fecha = st.selectbox("📅 Período", ["Todos", "Hoy", "Esta semana", "Este mes"])

    params: List[Any] = []
    sql = """
      SELECT v.id, v.fecha, v.total, s.nombre AS socio
      FROM venta v
      JOIN socio s ON s.id = v.socio_id
      WHERE 1=1
    """

    if q.strip():
        sql += " AND s.nombre ILIKE %s"
        params.append(f"%{q}%")

    if filtro_fecha == "Hoy":
        sql += " AND DATE(v.fecha) = CURRENT_DATE"
    elif filtro_fecha == "Esta semana":
        sql += " AND v.fecha >= CURRENT_DATE - INTERVAL '7 days'"
    elif filtro_fecha == "Este mes":
        sql += (
            " AND EXTRACT(month FROM v.fecha) = EXTRACT(month FROM CURRENT_DATE)"
            " AND EXTRACT(year FROM v.fecha) = EXTRACT(year FROM CURRENT_DATE)"
        )

    sql += " ORDER BY v.id DESC LIMIT 200"

    ventas = query(sql, params)

    for v in ventas or []:
        v["fecha"] = _to_datetime(v.get("fecha"))

    if ventas:
        total_ventas = sum(float(v.get("total", 0) or 0) for v in ventas)
        st.metric("💰 Total en ventas mostradas", _fmt_money(total_ventas), f"{len(ventas)} ventas")

        st.dataframe(
            ventas,
            use_container_width=True,
            column_config={
                "total": st.column_config.NumberColumn("Total", format="S/ %.2f"),
                "fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm"),
                "socio": "Socio",
                "id": "ID",
            }
        )

        st.markdown("### 🔍 Detalle de venta")
        sel = st.selectbox(
            "Seleccionar venta para ver detalle:",
            ventas,
            format_func=lambda v: (
                f"Venta #{v['id']} - {v['socio']} - {_fmt_money(v.get('total', 0))} "
                f"({v['fecha'].strftime('%d/%m/%Y') if isinstance(v.get('fecha'), datetime) else '—'})"
            )
        )

        if sel:
            det = query("""
                SELECT vi.id, p.nombre, vi.cantidad, vi.precio_unitario, vi.subtotal
                FROM venta_item vi
                JOIN producto p ON p.id = vi.producto_id
                WHERE vi.venta_id = %s
                ORDER BY vi.id
            """, (sel["id"],))

            if det:
                st.dataframe(
                    det,
                    use_container_width=True,
                    column_config={
                        "precio_unitario": st.column_config.NumberColumn("Precio Unit.", format="S/ %.2f"),
                        "subtotal": st.column_config.NumberColumn("Subtotal", format="S/ %.2f"),
                        "cantidad": st.column_config.NumberColumn("Cant.", format="%.0f"),
                        "nombre": "Producto",
                        "id": "ID Item",
                    }
                )

                if st.button("📄 Ver recibo"):
                    st.markdown("### 📄 Recibo de Venta")
                    mostrar_recibo_streamlit(sel, det)

            if has_permission("sales_refund"):
                st.markdown("### ⚠️ Anular venta")
                st.warning("Esta acción devolverá el stock y eliminará permanentemente la venta.")

                if st.button("🗑️ Anular venta", type="secondary"):
                    try:
                        with db_cursor(commit=True) as cur:
                            # Devolver stock
                            cur.execute("SELECT producto_id, cantidad FROM venta_item WHERE venta_id = %s", (sel["id"],))
                            for r in cur.fetchall():
                                cur.execute("UPDATE producto SET stock = stock + %s WHERE id = %s", (r["cantidad"], r["producto_id"]))
                            # Eliminar registros
                            cur.execute("DELETE FROM venta_item WHERE venta_id = %s", (sel["id"],))
                            cur.execute("DELETE FROM venta WHERE id = %s", (sel["id"],))

                        st.success(f"✅ Venta #{sel['id']} anulada correctamente. Stock devuelto.")
                        st.rerun()

                    except Exception as e:
                        st.error(f"❌ Error al anular la venta: {str(e)}")
            else:
                st.info("ℹ️ No tienes permiso para anular ventas.")
    else:
        st.info("📭 No se encontraron ventas con los filtros aplicados.")
