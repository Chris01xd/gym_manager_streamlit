# pages/02_Ventas.py
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

def generar_recibo_html(venta_data, items_data):
    """Genera el HTML del recibo de venta con diseño mejorado"""
    fecha_formateada = venta_data['fecha'].strftime("%d/%m/%Y %H:%M")
    
    items_html = ""
    for item in items_data:
        items_html += f"""
        <tr>
            <td style="border-bottom: 1px dashed #ccc; padding: 8px 0;">{item['nombre']}</td>
            <td style="text-align: center; border-bottom: 1px dashed #ccc; padding: 8px 0;">{item['cantidad']}</td>
            <td style="text-align: right; border-bottom: 1px dashed #ccc; padding: 8px 0;">S/ {item['precio_unitario']:.2f}</td>
            <td style="text-align: right; border-bottom: 1px dashed #ccc; padding: 8px 0;">S/ {item['subtotal']:.2f}</td>
        </tr>
        """
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: 'Courier New', monospace;
                max-width: 400px;
                margin: 0 auto;
                padding: 20px;
                background: white;
                color: black;
            }}
            .header {{
                text-align: center;
                border-bottom: 2px solid #333;
                padding-bottom: 10px;
                margin-bottom: 15px;
            }}
            .gym-name {{
                font-size: 18px;
                font-weight: bold;
                margin-bottom: 5px;
            }}
            .recibo-title {{
                font-size: 16px;
                font-weight: bold;
                margin-top: 10px;
            }}
            .info-row {{
                display: flex;
                justify-content: space-between;
                margin: 8px 0;
                padding: 2px 0;
            }}
            .label {{
                font-weight: bold;
                min-width: 120px;
            }}
            .value {{
                text-align: right;
                flex: 1;
            }}
            .separator {{
                border-bottom: 1px dashed #666;
                margin: 15px 0;
                height: 1px;
            }}
            .total {{
                font-size: 18px;
                font-weight: bold;
                text-align: center;
                padding: 10px;
                border: 2px solid #333;
                margin: 15px 0;
            }}
            .footer {{
                text-align: center;
                font-size: 12px;
                margin-top: 20px;
                border-top: 1px solid #333;
                padding-top: 10px;
            }}
            .numero-recibo {{
                text-align: center;
                font-size: 14px;
                margin: 10px 0;
            }}
            .items-table {{
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
            }}
            .items-table th {{
                border-bottom: 1px solid #000;
                padding: 8px 0;
                text-align: left;
            }}
            .items-table th:nth-child(2) {{
                text-align: center;
            }}
            .items-table th:nth-child(3), 
            .items-table th:nth-child(4) {{
                text-align: right;
            }}
            @media print {{
                body {{ 
                    margin: 0;
                    padding: 10px;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="header">
            <div class="gym-name">🏪 TIENDA</div>
            <div class="recibo-title">RECIBO DE VENTA</div>
        </div>
        
        <div class="numero-recibo">
            <strong>N° {venta_data['id']:06d}</strong>
        </div>
        
        <div class="info-row">
            <span class="label">Fecha:</span>
            <span class="value">{fecha_formateada}</span>
        </div>
        
        <div class="info-row">
            <span class="label">Cliente:</span>
            <span class="value">{venta_data['socio']}</span>
        </div>
        
        <div class="separator"></div>
        
        <table class="items-table">
            <thead>
                <tr>
                    <th>Producto</th>
                    <th>Cant</th>
                    <th>P.Unit</th>
                    <th>Subtotal</th>
                </tr>
            </thead>
            <tbody>
                {items_html}
            </tbody>
        </table>
        
        <div class="separator"></div>
        
        <div class="total">
            TOTAL: S/ {venta_data['total']:,.2f}
        </div>
        
        <div class="separator"></div>
        
        <div class="footer">
            <div>¡Gracias por su compra!</div>
            <div style="margin-top: 10px; font-size: 10px;">
                Atendido por: {st.session_state.get('user', {}).get('email', 'Sistema')}
            </div>
        </div>
    </body>
    </html>
    """
    return html

def mostrar_recibo_interactivo(venta_data, items_data):
    """Muestra el recibo en la interfaz de Streamlit"""
    st.success(f"🎉 ¡Venta registrada exitosamente! (ID: {venta_data['id']})")
    
    # Generar el HTML del recibo
    recibo_html = generar_recibo_html(venta_data, items_data)
    
    # Mostrar el recibo en un contenedor especial
    st.markdown("### 📄 Recibo de Venta")
    
    # Crear dos columnas: una para el recibo y otra para las acciones
    col1, col2 = st.columns([2, 1])
    
    with col1:
        # Mostrar el recibo usando componente HTML
        st.components.v1.html(recibo_html, height=600, scrolling=True)
    
    with col2:
        st.markdown("#### Acciones")
        
        # Botón para descargar como HTML
        st.download_button(
            label="📄 Descargar Recibo (HTML)",
            data=recibo_html,
            file_name=f"recibo_venta_{venta_data['id']:06d}.html",
            mime="text/html",
            use_container_width=True
        )
        
        # Información adicional
        st.info("💡 **Tip:** Puedes abrir el archivo HTML descargado en tu navegador e imprimirlo desde allí.")
        
        # Botón para limpiar y hacer otra venta
        if st.button("➕ Nueva Venta", use_container_width=True):
            # Limpiar el estado del recibo
            if 'mostrar_recibo_venta' in st.session_state:
                del st.session_state['mostrar_recibo_venta']
            if 'ultima_venta' in st.session_state:
                del st.session_state['ultima_venta']
            if 'venta_items' in st.session_state:
                st.session_state["venta_items"] = []
            st.rerun()

# ---------------------------------------
# UI
# ---------------------------------------
tab_nueva, tab_listado = st.tabs(["➕ Nueva venta", "📋 Listado / Anular"])

# --------- NUEVA VENTA ----------
with tab_nueva:
    if not has_permission("sales_create"):
        st.info("No tienes permiso para crear ventas.")
    else:
        # Verificar si hay que mostrar un recibo
        if st.session_state.get('mostrar_recibo_venta') and st.session_state.get('ultima_venta'):
            mostrar_recibo_interactivo(st.session_state['ultima_venta']['venta'], 
                                      st.session_state['ultima_venta']['items'])
        else:
            # Consultar socios y productos (con filtro activo y stock > 0 para mejor UX)
            socios = query("SELECT id, nombre FROM socio ORDER BY id DESC LIMIT 300")
            # CAMBIO: Filtrar productos con stock > 0 para evitar confusión
            prods = query("SELECT id, nombre, precio, stock FROM producto WHERE activo IS TRUE AND stock > 0 ORDER BY nombre")

            if not socios:
                st.warning("Necesitas al menos 1 socio registrado.")
            elif not prods:
                st.warning("No hay productos activos con stock disponible.")
            else:
                socio = st.selectbox("Socio", socios, format_func=lambda s: f"{s['id']} - {s['nombre']}")

                st.markdown("### Ítems")
                # Inicializar carrito en session_state
                if "venta_items" not in st.session_state:
                    st.session_state["venta_items"] = []

                # Formulario para agregar productos
                with st.form("f_add_item", clear_on_submit=True):
                    col1, col2, col3 = st.columns([3,1,1])
                    with col1:
                        prod = st.selectbox(
                            "Producto",
                            prods,
                            format_func=lambda p: f"{p['nombre']} - S/{p['precio']:.2f} (Stock: {p['stock']})",
                            key="prod_select"
                        )
                    with col2:
                        # Validar que hay stock disponible
                        if prod and prod["stock"] > 0:
                            # Calcular stock disponible considerando lo que ya está en el carrito
                            stock_en_carrito = 0
                            for item in st.session_state["venta_items"]:
                                if item["producto_id"] == prod["id"]:
                                    stock_en_carrito = item["cantidad"]
                                    break
                            
                            max_disponible = int(prod["stock"]) - stock_en_carrito
                            max_cant = max(1, max_disponible)
                            
                            cant = st.number_input("Cant.", min_value=1, value=1, step=1, max_value=max_cant)
                        else:
                            cant = st.number_input("Cant.", min_value=1, value=1, step=1, disabled=True)
                            
                    with col3:
                        add = st.form_submit_button("➕ Agregar", disabled=(not prod or prod["stock"] <= 0))

                # Procesar adición de producto
                if add and prod:
                    try:
                        st.session_state["venta_items"] = merge_or_append_item(st.session_state["venta_items"], prod, cant)
                        st.success(f"✅ Agregado: {prod['nombre']} x {int(cant)}")
                        st.rerun()  # Actualizar la interfaz
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")

                # Mostrar carrito actual
                items = st.session_state["venta_items"]
                if items:
                    # Botón para eliminar items individuales
                    st.markdown("**Carrito actual:**")
                    items_display = []
                    for i, item in enumerate(items):
                        items_display.append({
                            "Producto": item["nombre"],
                            "Cantidad": item["cantidad"],
                            "P.Unit": f"S/ {item['precio']:.2f}",
                            "Subtotal": f"S/ {item['subtotal']:.2f}",
                            "Acciones": f"🗑️ Eliminar"
                        })
                    
                    # Mostrar tabla con opción de eliminar
                    for i, item_display in enumerate(items_display):
                        col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                        with col1:
                            st.write(item_display["Producto"])
                        with col2:
                            st.write(item_display["Cantidad"])
                        with col3:
                            st.write(item_display["P.Unit"])
                        with col4:
                            st.write(item_display["Subtotal"])
                        with col5:
                            if st.button("🗑️", key=f"del_{i}", help="Eliminar item"):
                                st.session_state["venta_items"].pop(i)
                                st.rerun()

                    # Calcular y mostrar total
                    total = round(sum(it["subtotal"] for it in items), 2)
                    st.markdown(f"### **Total: S/ {total:,.2f}**")

                    # Controles de venta
                    col_confirmar, col_limpiar, col_fecha = st.columns([1,1,2])
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
                                # 1) Crear cabecera de venta
                                cur.execute(
                                    "INSERT INTO venta(socio_id, fecha, total) VALUES (%s, %s, %s) RETURNING id",
                                    (socio["id"], datetime.combine(fecha_venta, datetime.now().time()), total)
                                )
                                venta_id = cur.fetchone()["id"]

                                # 2) Insertar ítems con validación de stock
                                for it in items:
                                    add_item_with_stock_guard(cur, venta_id, it)

                                # 3) Recalcular total final
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
                                total_final = cur.fetchone()["total"]

                            # 4) Obtener datos para el recibo
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

                            # Guardar en session state y activar vista de recibo
                            st.session_state['ultima_venta'] = {
                                'venta': venta_completa,
                                'items': items_recibo
                            }
                            st.session_state['mostrar_recibo_venta'] = True
                            
                            # Rerun para mostrar el recibo
                            st.rerun()

                        except Exception as e:
                            st.error(f"❌ Error al registrar la venta: {str(e)}")
                else:
                    st.info("📦 Agrega productos al carrito para continuar...")
                    
                    # Mostrar productos disponibles como ayuda
                    if prods:
                        st.markdown("**Productos disponibles:**")
                        for prod in prods[:5]:  # Mostrar solo los primeros 5
                            st.write(f"• {prod['nombre']} - S/{prod['precio']:.2f} (Stock: {prod['stock']})")
                        if len(prods) > 5:
                            st.write(f"... y {len(prods) - 5} productos más")

# --------- LISTADO / ANULAR ----------
with tab_listado:
    require_perm("sales_read")
    st.subheader("📋 Ventas recientes")

    # Filtros de búsqueda
    col_busq, col_fecha = st.columns([2, 1])
    with col_busq:
        q = st.text_input("🔍 Buscar por socio (nombre)")
    with col_fecha:
        filtro_fecha = st.selectbox("📅 Período", ["Todos", "Hoy", "Esta semana", "Este mes"])

    # Construir consulta con filtros
    params = []
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
        sql += " AND EXTRACT(month FROM v.fecha) = EXTRACT(month FROM CURRENT_DATE) AND EXTRACT(year FROM v.fecha) = EXTRACT(year FROM CURRENT_DATE)"

    sql += " ORDER BY v.id DESC LIMIT 200"

    ventas = query(sql, params)
    
    if ventas:
        # Mostrar resumen
        total_ventas = sum(v['total'] for v in ventas)
        st.metric("💰 Total en ventas mostradas", f"S/ {total_ventas:,.2f}", f"{len(ventas)} ventas")
        
        # Tabla de ventas
        st.dataframe(
            ventas, 
            use_container_width=True,
            column_config={
                "total": st.column_config.NumberColumn("Total", format="S/ %.2f"),
                "fecha": st.column_config.DatetimeColumn("Fecha", format="DD/MM/YYYY HH:mm")
            }
        )

        # Detalle de venta seleccionada
        if ventas:
            st.markdown("### 🔍 Detalle de venta")
            sel = st.selectbox(
                "Seleccionar venta para ver detalle:",
                ventas,
                format_func=lambda v: f"Venta #{v['id']} - {v['socio']} - S/{v['total']:.2f} ({v['fecha'].strftime('%d/%m/%Y')})"
            )

            if sel:
                # Obtener detalle de items
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
                            "subtotal": st.column_config.NumberColumn("Subtotal", format="S/ %.2f")
                        }
                    )
                    
                    # Generar recibo de la venta seleccionada
                    if st.button("📄 Ver recibo"):
                        recibo_html = generar_recibo_html(sel, det)
                        st.markdown("### 📄 Recibo")
                        st.components.v1.html(recibo_html, height=600, scrolling=True)
                        
                        # Botón para descargar
                        st.download_button(
                            label="📄 Descargar Recibo",
                            data=recibo_html,
                            file_name=f"recibo_venta_{sel['id']:06d}.html",
                            mime="text/html"
                        )

                # Opción de anular venta
                if has_permission("sales_refund"):
                    st.markdown("### ⚠️ Anular venta")
                    st.warning("Esta acción devolverá el stock y eliminará permanentemente la venta.")
                    
                    if st.button("🗑️ Anular venta", type="secondary"):
                        try:
                            with db_cursor(commit=True) as cur:
                                # 1) Devolver stock
                                cur.execute("SELECT producto_id, cantidad FROM venta_item WHERE venta_id = %s", (sel["id"],))
                                for r in cur.fetchall():
                                    cur.execute("UPDATE producto SET stock = stock + %s WHERE id = %s", (r["cantidad"], r["producto_id"]))
                                
                                # 2) Eliminar registros
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
