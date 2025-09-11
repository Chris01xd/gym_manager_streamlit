import streamlit as st
from datetime import date, datetime, time, timedelta
from io import StringIO
import csv

from app.lib.auth import require_perm, has_permission
from app.lib.db import query, db_cursor
from app.lib.ui import load_base_css

st.set_page_config(page_title="Pagos", page_icon="💳", layout="wide")
load_base_css()
st.title("💳 Pagos")

require_perm("payments_read")

# ------------------ Helpers ------------------
MEDIOS = ["Efectivo", "Tarjeta", "Transferencia", "Yape", "Plin", "POS", "Otro"]

def to_csv(rows, headers):
    sio = StringIO()
    writer = csv.DictWriter(sio, fieldnames=headers)
    writer.writeheader()
    for r in rows:
        writer.writerow({k: r.get(k) for k in headers})
    return sio.getvalue()

def auditoria(cur, accion, entidad, entidad_id=None, detalle=None):
    """Audita si la tabla auditoria existe (opcional)."""
    try:
        u = st.session_state.get("user") or {}
        uid = u.get("id")
        cur.execute("""
            INSERT INTO auditoria (usuario_id, accion, entidad, entidad_id, detalle)
            VALUES (%s, %s, %s, %s, %s::jsonb)
        """, (uid, accion, entidad, entidad_id, detalle))
    except Exception:
        # si no existe la tabla o falla, no romper el flujo
        pass

def generar_recibo_html(pago_data):
    """Genera HTML para el recibo de pago"""
    fecha_formato = pago_data['fecha'].strftime('%d/%m/%Y %H:%M') if isinstance(pago_data['fecha'], datetime) else pago_data['fecha']
    
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
            <div class="gym-name">🏋️ GYM MANAGER</div>
            <div>RUC: 20123456789</div>
            <div class="recibo-title">RECIBO DE PAGO</div>
        </div>
        
        <div class="numero-recibo">
            <strong>N° {pago_data['id']:06d}</strong>
        </div>
        
        <div class="info-row">
            <span class="label">Fecha:</span>
            <span class="value">{fecha_formato}</span>
        </div>
        
        <div class="info-row">
            <span class="label">Cliente:</span>
            <span class="value">{pago_data['socio']}</span>
        </div>
        
        <div class="info-row">
            <span class="label">Concepto:</span>
            <span class="value">{pago_data['concepto']}</span>
        </div>
        
        <div class="info-row">
            <span class="label">Medio de Pago:</span>
            <span class="value">{pago_data['medio']}</span>
        </div>
        
        {f'''<div class="info-row">
            <span class="label">Referencia:</span>
            <span class="value">{pago_data['ref_externa']}</span>
        </div>''' if pago_data.get('ref_externa') else ''}
        
        <div class="separator"></div>
        
        <div class="total">
            TOTAL: S/ {pago_data['monto']:,.2f}
        </div>
        
        <div class="separator"></div>
        
        <div class="footer">
            <div>¡Gracias por tu pago!</div>
            <div>Conserva este recibo como comprobante</div>
            <div style="margin-top: 10px; font-size: 10px;">
                Atendido por: {st.session_state.get('user', {}).get('email', 'Sistema')}
            </div>
        </div>
    </body>
    </html>
    """
    return html

def mostrar_recibo_interactivo(pago_data):
    """Muestra el recibo en la interfaz de Streamlit"""
    st.success("✅ Pago registrado exitosamente")
    
    # Generar el HTML del recibo
    recibo_html = generar_recibo_html(pago_data)
    
    # Mostrar el recibo en un contenedor especial
    st.markdown("### 🧾 Recibo Generado")
    
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
            file_name=f"recibo_{pago_data['id']:06d}.html",
            mime="text/html",
            use_container_width=True
        )
        
        # Información adicional
        st.info("💡 **Tip:** Puedes abrir el archivo HTML descargado en tu navegador e imprimirlo desde allí.")
        
        # Botón para limpiar y hacer otro pago
        if st.button("➕ Registrar Nuevo Pago", use_container_width=True):
            # Limpiar el estado del recibo
            if 'mostrar_recibo' in st.session_state:
                del st.session_state['mostrar_recibo']
            if 'ultimo_pago' in st.session_state:
                del st.session_state['ultimo_pago']
            st.rerun()

# ------------------ Tabs ------------------
tab_nuevo, tab_listado = st.tabs(["➕ Registrar pago", "📋 Listado / Anular"])

# ================== NUEVO PAGO ==================
with tab_nuevo:
    if not has_permission("payments_create"):
        st.info("No tienes permiso para registrar pagos.")
    else:
        # Verificar si hay que mostrar un recibo
        if st.session_state.get('mostrar_recibo') and st.session_state.get('ultimo_pago'):
            mostrar_recibo_interactivo(st.session_state['ultimo_pago'])
        else:
            # Formulario normal de pago
            socios = query("SELECT id, nombre FROM socio ORDER BY nombre LIMIT 500")
            if not socios:
                st.warning("Primero crea un socio.")
            else:
                c1, c2 = st.columns([2, 1])
                with c1:
                    socio = st.selectbox("Socio", socios, format_func=lambda s: f"{s['nombre']} (#{s['id']})")
                with c2:
                    medio = st.selectbox("Medio de pago", MEDIOS, index=0)

                concepto = st.text_input("Concepto", placeholder="Mensualidad septiembre / Inscripción / Producto, etc.")
                monto = st.number_input("Monto (S/)", min_value=0.10, step=1.00, value=50.00, format="%.2f")
                ref = st.text_input("Referencia externa (opcional)", placeholder="N° operación, voucher, etc.")

                # Fecha/hora del pago
                colf1, colf2 = st.columns(2)
                with colf1:
                    f_pago = st.date_input("Fecha de pago", value=date.today())
                with colf2:
                    t_pago = st.time_input("Hora", value=datetime.now().time().replace(microsecond=0))

                guardar = st.button("💾 Guardar pago", type="primary", disabled=(not concepto or monto <= 0))

                if guardar:
                    try:
                        ts = datetime.combine(f_pago, t_pago)
                        with db_cursor(commit=True) as cur:
                            cur.execute("""
                                INSERT INTO pago (socio_id, concepto, monto, medio, ref_externa, fecha)
                                VALUES (%s, %s, %s, %s, %s, %s)
                                RETURNING id
                            """, (socio["id"], concepto.strip(), monto, medio, (ref or None), ts))
                            pid = cur.fetchone()["id"]
                            auditoria(cur,
                                      accion="crear_pago",
                                      entidad="pago",
                                      entidad_id=pid,
                                      detalle=f'{{"socio_id": {socio["id"]}, "monto": {monto}, "medio": "{medio}"}}')
                        
                        # Preparar datos para el recibo
                        pago_data = {
                            'id': pid,
                            'fecha': ts,
                            'socio': socio['nombre'],
                            'concepto': concepto.strip(),
                            'medio': medio,
                            'monto': monto,
                            'ref_externa': ref if ref else None
                        }
                        
                        # Guardar en session state y activar vista de recibo
                        st.session_state['ultimo_pago'] = pago_data
                        st.session_state['mostrar_recibo'] = True
                        
                        # Rerun para mostrar el recibo
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"No se pudo registrar el pago: {e}")

# ================== LISTADO ==================
with tab_listado:
    st.subheader("Búsqueda")
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        desde = st.date_input("Desde", value=date.today() - timedelta(days=7))
    with c2:
        hasta = st.date_input("Hasta", value=date.today())
    with c3:
        q_socio = st.text_input("Socio (nombre contiene)")
    with c4:
        q_medio = st.selectbox("Medio", ["(Todos)"] + MEDIOS)

    c5, c6 = st.columns(2)
    with c5:
        q_concepto = st.text_input("Concepto (contiene)")
    with c6:
        limite = st.selectbox("Límite", [50, 100, 200, 500, 1000], index=2)

    # rango inclusive del día "hasta"
    start = datetime.combine(desde, time.min)
    end = datetime.combine(hasta + timedelta(days=1), time.min)

    sql = """
    SELECT p.id, p.fecha, s.nombre AS socio, p.concepto, p.medio, p.monto, p.ref_externa
    FROM pago p
    JOIN socio s ON s.id = p.socio_id
    WHERE p.fecha >= %s AND p.fecha < %s
    """
    params = [start, end]

    if q_socio.strip():
        sql += " AND s.nombre ILIKE %s"
        params.append(f"%{q_socio}%")
    if q_concepto.strip():
        sql += " AND p.concepto ILIKE %s"
        params.append(f"%{q_concepto}%")
    if q_medio != "(Todos)":
        sql += " AND p.medio = %s"
        params.append(q_medio)

    sql += " ORDER BY p.fecha DESC, p.id DESC LIMIT %s"
    params.append(limite)

    rows = query(sql, tuple(params))

    # Totales del periodo filtrado
    total = sum(r["monto"] for r in rows) if rows else 0
    st.metric("Total en el periodo (S/)", f"{total:,.2f}")

    st.dataframe(rows, use_container_width=True)

    # Exportar CSV
    if rows:
        csv_data = to_csv(rows, headers=["id", "fecha", "socio", "concepto", "medio", "monto", "ref_externa"])
        st.download_button("⬇️ Exportar CSV", data=csv_data, file_name="pagos.csv", mime="text/csv")

    # Sección para regenerar recibos
    if rows:
        st.divider()
        st.markdown("### 🧾 Regenerar Recibo")
        sel_recibo = st.selectbox(
            "Selecciona el pago para regenerar su recibo",
            rows,
            format_func=lambda r: f"#{r['id']} | {r['fecha']} | {r['socio']} | S/ {r['monto']} | {r['concepto']}"
        )
        
        if st.button("📄 Generar Recibo"):
            pago_data = {
                'id': sel_recibo['id'],
                'fecha': sel_recibo['fecha'],
                'socio': sel_recibo['socio'],
                'concepto': sel_recibo['concepto'],
                'medio': sel_recibo['medio'],
                'monto': sel_recibo['monto'],
                'ref_externa': sel_recibo['ref_externa']
            }
            
            recibo_html = generar_recibo_html(pago_data)
            
            st.download_button(
                label="📄 Descargar Recibo",
                data=recibo_html,
                file_name=f"recibo_{pago_data['id']:06d}.html",
                mime="text/html"
            )
            
            # Mostrar preview del recibo
            with st.expander("👁️ Vista Previa del Recibo"):
                st.components.v1.html(recibo_html, height=400, scrolling=True)

    # Anular / reversar
    if rows and has_permission("payments_refund"):
        st.divider()
        st.markdown("### Anular / Reversar pago")
        sel = st.selectbox(
            "Selecciona el pago",
            rows,
            format_func=lambda r: f"#{r['id']} | {r['fecha']} | {r['socio']} | S/ {r['monto']} | {r['medio']} | {r['concepto']}"
        )
        motivo = st.text_input("Motivo de anulación (se registrará en auditoría)")
        if st.button("🧾 Generar reverso (asiento negativo)"):
            try:
                with db_cursor(commit=True) as cur:
                    # crear contrapartida negativa (no borramos historial)
                    cur.execute("""
                        INSERT INTO pago (socio_id, concepto, monto, medio, ref_externa, fecha)
                        VALUES (
                            (SELECT socio_id FROM pago WHERE id=%s),
                            %s,
                            -(SELECT monto FROM pago WHERE id=%s),
                            'anulacion',
                            %s,
                            now()
                        )
                        RETURNING id
                    """, (sel["id"], f"ANULACIÓN #{sel['id']}: {motivo or sel['concepto']}", sel["id"], f"reversa de #{sel['id']}"))
                    rid = cur.fetchone()["id"]
                    auditoria(cur,
                              accion="reverso_pago",
                              entidad="pago",
                              entidad_id=rid,
                              detalle=f'{{"reversa_de": {sel["id"]}}}')
                st.success(f"Pago reversado con asiento #{rid}")
                st.rerun()
            except Exception as e:
                st.error(f"No se pudo reversar: {e}")
    elif rows:
        st.info("No tienes permiso para anular/reversar pagos.")
