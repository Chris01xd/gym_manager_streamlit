# pages/02_Ventas.py  (o el nombre que uses)
import streamlit as st
from datetime import datetime, date

from app.lib.auth import require_login, has_permission, require_perm
from app.lib.db import query, db_cursor
from app.lib.ui import load_base_css

st.set_page_config(page_title="Ventas", page_icon="💵", layout="wide")
load_base_css()
st.title("💵 Ventas")

require_login()

# ---------------------------------------
# Helpers
# ---------------------------------------
def add_item_with_stock_guard(cur, venta_id, it):
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
            %s,                         -- venta_id
            %s,                         -- producto_id
            %s,                         -- cantidad (integer en tu esquema)
            %s::numeric(12,2),          -- precio
            %s::numeric(12,2),          -- precio_unitario
            ROUND((%s::numeric * %s::numeric), 2)  -- subtotal = precio * cantidad
        FROM upd
        RETURNING id
    )
    SELECT id FROM ins;
    """
    params = (
        it["cantidad"], it["producto_id"], it["cantidad"],     # upd
        venta_id, it["producto_id"], it["cantidad"],           # ins (claves y cantidad)
        it["precio"], it["precio"],                            # precio y precio_unitario
        it["precio"], it["cantidad"]                           # subtotal (precio * cantidad)
    )
    cur.execute(sql, params)
    row = cur.fetchone()
    if not row:
        raise Exception(f"Stock insuficiente para '{it['nombre']}' (id {it['producto_id']}).")

def merge_or_append_item(items, prod, cantidad):
    """
    Suma cantidades si el producto ya está en el carrito, validando no exceder stock.
    Devuelve la nueva lista.
    """
    new_items = items.copy()
    idx = next((i for i, x in enumerate(new_items) if x["producto_id"] == prod["id"]), None)

    if idx is None:
        if cantidad > prod["stock"]:
            raise ValueError(f"No hay stock suficiente. Disponible: {prod['stock']}.")
        new_items.append({
            "producto_id": prod["id"],
            "nombre": prod["nombre"],
            "precio": float(prod["precio"]),
            "cantidad": int(cantidad),
            "subtotal": round(float(prod["precio"]) * int(cantidad), 2)
        })
    else:
        nueva_cant = new_items[idx]["cantidad"] + int(cantidad)
        if nueva_cant > prod["stock"]:
            raise ValueError(f"No hay stock suficiente. En carrito: {new_items[idx]['cantidad']}, disponible: {prod['stock']}.")
        new_items[idx]["cantidad"] = nueva_cant
        new_items[idx]["subtotal"] = round(new_items[idx]["precio"] * nueva_cant, 2)

    return new_items

# ---------------------------------------
# UI
# ---------------------------------------
tab_nueva, tab_listado = st.tabs(["➕ Nueva venta", "📋 Listado / Anular"])

# --------- NUEVA VENTA ----------
with tab_nueva:
    if not has_permission("sales_create"):
        st.info("No tienes permiso para crear ventas.")
    else:
        socios = query("SELECT id, nombre FROM socio ORDER BY id DESC LIMIT 300")
        prods = query("SELECT id, nombre, precio, stock FROM producto WHERE activo IS TRUE ORDER BY nombre")

        if not socios or not prods:
            st.warning("Necesitas al menos 1 socio y 1 producto activo.")
        else:
            socio = st.selectbox("Socio", socios, format_func=lambda s: f"{s['id']} - {s['nombre']}")

            st.markdown("### Ítems")
            if "venta_items" not in st.session_state:
                st.session_state["venta_items"] = []

            with st.form("f_add_item", clear_on_submit=True):
                col1, col2, col3 = st.columns([3,1,1])
                with col1:
                    prod = st.selectbox(
                        "Producto",
                        prods,
                        format_func=lambda p: f"{p['nombre']} (S/{p['precio']}, stock {p['stock']})"
                    )
                with col2:
                    # Si el stock es 0, evita pedir cantidad inválida
                    max_cant = int(prod["stock"]) if int(prod["stock"]) > 0 else 1
                    cant = st.number_input("Cant.", min_value=1, value=1, step=1, max_value=max_cant)
                with col3:
                    add = st.form_submit_button("➕ Agregar", disabled=(prod["stock"] <= 0))

            if add:
                try:
                    st.session_state["venta_items"] = merge_or_append_item(st.session_state["venta_items"], prod, cant)
                    st.success(f"Agregado: {prod['nombre']} x {int(cant)}")
                except Exception as e:
                    st.error(str(e))

            # Tabla carrito
            items = st.session_state["venta_items"]
            if items:
                st.table([
                    {"Producto": it["nombre"], "Cant": it["cantidad"], "P.Unit": it["precio"], "Subtotal": it["subtotal"]}
                    for it in items
                ])
                total = round(sum(it["subtotal"] for it in items), 2)
                st.subheader(f"Total: S/ {total:,.2f}")

                colA, colB, colC = st.columns([1,1,2])
                with colA:
                    confirmar = st.button("💾 Confirmar venta")
                with colB:
                    limpiar = st.button("🧹 Limpiar ítems")
                with colC:
                    fecha_venta = st.date_input("Fecha", value=date.today())

                if limpiar:
                    st.session_state["venta_items"] = []
                    st.rerun()

                if confirmar:
                    try:
                        with db_cursor(commit=True) as cur:
                            # 1) Crear cabecera con total preliminar (se recalcula luego)
                            cur.execute(
                                "INSERT INTO venta(socio_id, fecha, total) VALUES (%s, %s, %s) RETURNING id",
                                (socio["id"], datetime.combine(fecha_venta, datetime.now().time()), total)
                            )
                            venta_id = cur.fetchone()["id"]

                            # 2) Insertar ítems con guardas (stock + precio NOT NULL)
                            for it in items:
                                add_item_with_stock_guard(cur, venta_id, it)

                            # 3) Recalcular total por seguridad según lo realmente insertado
                            cur.execute("""
                                UPDATE venta v
                                SET total = COALESCE((
                                    SELECT SUM(subtotal)::numeric(12,2)
                                    FROM venta_item vi
                                    WHERE vi.venta_id = v.id
                                ), 0)
                                WHERE v.id = %s
                            """, (venta_id,))

                        st.success(f"Venta creada (ID {venta_id})")
                        st.session_state["venta_items"] = []
                        st.rerun()

                    except Exception as e:
                        st.error(f"No se pudo registrar la venta: {e}")
            else:
                st.info("Agrega productos al carrito.")

# --------- LISTADO / ANULAR ----------
with tab_listado:
    require_perm("sales_read")
    st.subheader("Ventas recientes")

    q = st.text_input("Buscar por socio (nombre)")
    params = ()
    sql = """
      SELECT v.id, v.fecha, v.total, s.nombre AS socio
      FROM venta v
      JOIN socio s ON s.id = v.socio_id
    """
    if q.strip():
        sql += "WHERE s.nombre ILIKE %s "
        params = (f"%{q}%",)
    sql += "ORDER BY v.id DESC LIMIT 200"

    ventas = query(sql, params)
    st.dataframe(ventas, use_container_width=True)

    if ventas:
        sel = st.selectbox(
            "Venta",
            ventas,
            format_func=lambda v: f"{v['id']} - {v['socio']} @ {v['fecha']}  (S/{v['total']})"
        )

        det = query("""
            SELECT vi.id, p.nombre, vi.cantidad, vi.precio_unitario, vi.subtotal
            FROM venta_item vi
            JOIN producto p ON p.id = vi.producto_id
            WHERE vi.venta_id = %s
        """, (sel["id"],))

        st.markdown("### Detalle")
        st.dataframe(det, use_container_width=True)

        if has_permission("sales_refund"):
            if st.button("🧾 Anular venta (devuelve stock)"):
                try:
                    with db_cursor(commit=True) as cur:
                        # 1) Devolver stock de cada ítem
                        cur.execute("SELECT producto_id, cantidad FROM venta_item WHERE venta_id = %s", (sel["id"],))
                        for r in cur.fetchall():
                            cur.execute("UPDATE producto SET stock = stock + %s WHERE id = %s", (r["cantidad"], r["producto_id"]))
                        # 2) Borrar ítems y cabecera
                        cur.execute("DELETE FROM venta_item WHERE venta_id = %s", (sel["id"],))
                        cur.execute("DELETE FROM venta WHERE id = %s", (sel["id"],))
                    st.success("Venta anulada")
                    st.rerun()
                except Exception as e:
                    st.error(f"No se pudo anular: {e}")
        else:
            st.info("No tienes permiso para anular ventas.")
