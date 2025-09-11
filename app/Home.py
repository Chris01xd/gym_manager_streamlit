import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from lib.auth import login_form, has_permission
from lib.sp_wrappers import kpis
from lib.db import query

st.set_page_config(page_title="Gym Manager", page_icon="🏋️", layout="wide")

# Header
left, right = st.columns([0.8, 0.2])
with left:
    st.title("🏋️ Gym Manager — Dashboard")
with right:
    if st.session_state.get("user"):
        if st.button("🚪 Salir", type="primary", help="Cerrar sesión"):
            try:
                from lib.auth import logout
                logout()
            except Exception:
                for k in ("user", "permissions", "jwt", "auth_user", "session_id", "col_index"):
                    st.session_state.pop(k, None)
            st.success("Sesión cerrada.")
            st.rerun()

# Si no hay sesión: muestra login
if not st.session_state.get("user"):
    login_form()
else:
    # Usuario logueado
    u = st.session_state["user"]
    st.success(f"Hola, {u['email']} ({u['rol']})")

    # === KPIs PRINCIPALES ===
    st.header("📊 Resumen Ejecutivo")
    
    try:
        data = kpis()
        d = data[0] if data else {}
        socios = d.get("socios", "—")
        activas = d.get("membresias_activas", "—")
        accesos_hoy = d.get("accesos_hoy", "—")
    except Exception:
        socios = query("SELECT COUNT(*) c FROM socio")[0]["c"]
        activas = query("SELECT COUNT(*) c FROM membresia WHERE estado='activa' AND fecha_fin>=CURRENT_DATE")[0]["c"]
        accesos_hoy = query("SELECT COUNT(*) c FROM acceso WHERE fecha_entrada::date=CURRENT_DATE")[0]["c"]

    # KPIs adicionales
    try:
        # Aforo actual por sede
        aforo_data = query("""
            SELECT s.nombre, sp_aforo_actual(s.id) as aforo_actual
            FROM sede s ORDER BY s.nombre
        """)
        
        # Ventas del día
        ventas_hoy = query("""
            SELECT COALESCE(SUM(total), 0)::numeric(10,2) as total
            FROM venta WHERE fecha::date = CURRENT_DATE
        """)[0]["total"] if query("SELECT COUNT(*) c FROM venta WHERE fecha::date = CURRENT_DATE")[0]["c"] > 0 else 0

        # Próximas clases (hoy)
        clases_hoy = query("""
            SELECT COUNT(*) c FROM clase 
            WHERE fecha_hora::date = CURRENT_DATE AND estado = 'programada'
        """)[0]["c"]

        # Membresías que vencen en 7 días
        vencimientos = query("""
            SELECT COUNT(*) c FROM membresia 
            WHERE estado = 'activa' AND fecha_fin BETWEEN CURRENT_DATE AND CURRENT_DATE + 7
        """)[0]["c"]

    except Exception as e:
        st.error(f"Error obteniendo datos adicionales: {e}")
        aforo_data = []
        ventas_hoy = 0
        clases_hoy = 0
        vencimientos = 0

    # Mostrar KPIs en columnas
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric("👥 Socios Totales", socios)
    with col2:
        st.metric("💳 Membresías Activas", activas)
    with col3:
        st.metric("🚪 Accesos Hoy", accesos_hoy)
    with col4:
        st.metric("💰 Ventas Hoy", f"S/. {ventas_hoy}")
    with col5:
        st.metric("📅 Clases Hoy", clases_hoy)

    # === ALERTAS ===
    if vencimientos > 0:
        st.warning(f"⚠️ {vencimientos} membresías vencen en los próximos 7 días")

    # === AFORO POR SEDE ===
    if aforo_data:
        st.subheader("🏢 Aforo Actual por Sede")
        aforo_cols = st.columns(len(aforo_data))
        for i, sede_info in enumerate(aforo_data):
            with aforo_cols[i]:
                st.metric(
                    f"📍 {sede_info['nombre']}", 
                    f"{sede_info['aforo_actual']} personas",
                    help="Personas actualmente en la sede"
                )

    st.divider()

    # === GRÁFICOS DE TENDENCIAS ===
    st.header("📈 Tendencias")
    
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        st.subheader("Accesos por Día (Última Semana)")
        try:
            accesos_semana = query("""
                SELECT 
                    fecha_entrada::date as fecha,
                    COUNT(*) as accesos
                FROM acceso 
                WHERE fecha_entrada >= CURRENT_DATE - 7
                GROUP BY fecha_entrada::date
                ORDER BY fecha
            """)
            if accesos_semana:
                df_accesos = pd.DataFrame(accesos_semana)
                st.line_chart(df_accesos.set_index('fecha'))
            else:
                st.info("No hay datos de accesos en la última semana")
        except Exception as e:
            st.error(f"Error cargando gráfico de accesos: {e}")

    with chart_col2:
        st.subheader("Ventas por Día (Última Semana)")
        try:
            ventas_semana = query("""
                SELECT 
                    fecha::date as fecha,
                    SUM(total) as total_ventas
                FROM venta 
                WHERE fecha >= CURRENT_DATE - 7
                GROUP BY fecha::date
                ORDER BY fecha
            """)
            if ventas_semana:
                df_ventas = pd.DataFrame(ventas_semana)
                st.line_chart(df_ventas.set_index('fecha'))
            else:
                st.info("No hay datos de ventas en la última semana")
        except Exception as e:
            st.error(f"Error cargando gráfico de ventas: {e}")

    st.divider()

    # === ATAJOS RÁPIDOS ===
    st.header("🚀 Acceso Rápido")

    # Reset contador de columnas
    st.session_state["col_index"] = 0
    cols = st.columns(3)

    def add_link(path, label, icon):
        """Agrega un link en la columna que toque"""
        nonlocal_index = st.session_state.get("col_index", 0)
        with cols[nonlocal_index % 3]:
            st.page_link(path, label=label, icon=icon)
        st.session_state["col_index"] = nonlocal_index + 1

    # Enlaces según permisos
    if has_permission("socios_read"):
        add_link("pages/1_Socios.py", "Gestión de Socios", "👤")
    if has_permission("membership_assign") or has_permission("plans_manage"):
        add_link("pages/2_Membresias.py", "Membresías y Planes", "💳")
    if has_permission("classes_publish") or has_permission("reservations_create"):
        add_link("pages/3_Clases.py", "Clases y Reservas", "📆")
    if has_permission("access_entry") or has_permission("access_exit"):
        add_link("pages/4_Accesos_Aforo.py", "Control de Acceso", "🚪")
    if has_permission("products_manage"):
        add_link("pages/7_Productos.py", "Inventario", "🛒")
    if has_permission("sales_read") or has_permission("sales_create"):
        add_link("pages/8_Ventas.py", "Punto de Venta", "💵")
    if has_permission("payments_read") or has_permission("payments_create"):
        add_link("pages/10_Pagos.py", "Gestión de Pagos", "💳")
    if has_permission("reports_view"):
        add_link("pages/5_Reportes.py", "Reportes", "📊")
    if has_permission("users_manage"):
        add_link("pages/6_Usuarios.py", "Administración", "👥")
    if has_permission("audit_view"):
        add_link("pages/9_Auditoria.py", "Auditoría", "📑")

    st.divider()

    # === INFORMACIÓN DETALLADA ===
    tab1, tab2, tab3, tab4 = st.tabs(["📅 Próximas Clases", "⏰ Actividad Reciente", "📋 Membresías por Vencer", "🏆 Top Productos"])

    with tab1:
        st.subheader("Clases Programadas (Próximas 48 horas)")
        try:
            clases = query("""
                SELECT 
                    c.id,
                    c.nombre,
                    s.nombre AS sede,
                    c.fecha_hora,
                    c.capacidad,
                    COUNT(r.id) as reservas,
                    (c.capacidad - COUNT(r.id)) as disponibles
                FROM clase c 
                JOIN sede s ON s.id = c.sede_id
                LEFT JOIN reserva r ON r.clase_id = c.id AND r.estado = 'confirmada'
                WHERE c.fecha_hora >= now() - interval '1 hour'
                  AND c.fecha_hora <= now() + interval '48 hours'
                  AND c.estado = 'programada'
                GROUP BY c.id, c.nombre, s.nombre, c.fecha_hora, c.capacidad
                ORDER BY c.fecha_hora
                LIMIT 20
            """)
            if clases:
                df_clases = pd.DataFrame(clases)
                df_clases['fecha_hora'] = pd.to_datetime(df_clases['fecha_hora'])
                st.dataframe(
                    df_clases[['nombre', 'sede', 'fecha_hora', 'reservas', 'disponibles']], 
                    use_container_width=True,
                    column_config={
                        'fecha_hora': st.column_config.DatetimeColumn(
                            'Fecha y Hora',
                            format='DD/MM/YYYY HH:mm'
                        )
                    }
                )
            else:
                st.info("No hay clases programadas en las próximas 48 horas")
        except Exception as e:
            st.error(f"Error cargando clases: {e}")

    with tab2:
        st.subheader("Últimos Accesos")
        try:
            accesos_recientes = query("""
                SELECT 
                    s.nombre as socio,
                    se.nombre as sede,
                    a.fecha_entrada,
                    CASE WHEN a.fecha_salida IS NULL THEN 'Dentro' ELSE 'Salió' END as estado
                FROM acceso a
                JOIN socio s ON s.id = a.socio_id
                JOIN sede se ON se.id = a.sede_id
                ORDER BY a.fecha_entrada DESC
                LIMIT 10
            """)
            if accesos_recientes:
                df_accesos = pd.DataFrame(accesos_recientes)
                df_accesos['fecha_entrada'] = pd.to_datetime(df_accesos['fecha_entrada'])
                st.dataframe(
                    df_accesos,
                    use_container_width=True,
                    column_config={
                        'fecha_entrada': st.column_config.DatetimeColumn(
                            'Hora de Entrada',
                            format='DD/MM/YYYY HH:mm'
                        )
                    }
                )
            else:
                st.info("No hay accesos recientes")
        except Exception as e:
            st.error(f"Error cargando accesos: {e}")

    with tab3:
        st.subheader("Membresías que Vencen Pronto")
        try:
            vencimientos_detalle = query("""
                SELECT 
                    s.nombre as socio,
                    s.telefono,
                    mp.nombre as plan,
                    m.fecha_fin,
                    (m.fecha_fin - CURRENT_DATE) as dias_restantes
                FROM membresia m
                JOIN socio s ON s.id = m.socio_id
                JOIN membresia_plan mp ON mp.id = m.plan_id
                WHERE m.estado = 'activa' 
                  AND m.fecha_fin BETWEEN CURRENT_DATE AND CURRENT_DATE + 15
                ORDER BY m.fecha_fin
            """)
            if vencimientos_detalle:
                df_venc = pd.DataFrame(vencimientos_detalle)
                st.dataframe(df_venc, use_container_width=True)
            else:
                st.success("No hay membresías por vencer en los próximos 15 días")
        except Exception as e:
            st.error(f"Error cargando vencimientos: {e}")

    with tab4:
        st.subheader("Productos Más Vendidos (Último Mes)")
        try:
            top_productos = query("""
                SELECT 
                    p.nombre,
                    SUM(vi.cantidad) as total_vendido,
                    SUM(vi.subtotal) as ingresos,
                    p.stock as stock_actual
                FROM venta_item vi
                JOIN producto p ON p.id = vi.producto_id
                JOIN venta v ON v.id = vi.venta_id
                WHERE v.fecha >= CURRENT_DATE - 30
                GROUP BY p.id, p.nombre, p.stock
                ORDER BY total_vendido DESC
                LIMIT 10
            """)
            if top_productos:
                df_productos = pd.DataFrame(top_productos)
                st.dataframe(df_productos, use_container_width=True)
            else:
                st.info("No hay ventas de productos en el último mes")
        except Exception as e:
            st.error(f"Error cargando productos: {e}")

    # === PIE DE PÁGINA ===
    st.divider()
    st.caption(f"🕒 Última actualización: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
