from .db import call_sp

def alta_socio(dni, nombre, email, telefono):
    return call_sp("sp_alta_socio", (dni, nombre, email, telefono))

def crear_membresia(socio_id, plan_id, fecha_inicio):
    return call_sp("sp_crear_membresia", (socio_id, plan_id, fecha_inicio))

def registrar_pago(socio_id, concepto, monto, medio, ref_externa):
    return call_sp("sp_registrar_pago", (socio_id, concepto, monto, medio, ref_externa))

def publicar_clase(sede_id, nombre, fecha_hora, capacidad):
    return call_sp("sp_publicar_clase", (sede_id, nombre, fecha_hora, capacidad))

def reservar_clase(socio_id, clase_id):
    return call_sp("sp_reservar_clase", (socio_id, clase_id))

def checkin_clase(reserva_id):
    return call_sp("sp_checkin_clase", (reserva_id,))

def registrar_acceso(socio_id, sede_id):
    return call_sp("sp_registrar_acceso", (socio_id, sede_id))

def registrar_salida(acceso_id):
    return call_sp("sp_registrar_salida", (acceso_id,))

def aforo_actual(sede_id):
    rows = call_sp("sp_aforo_actual", (sede_id,))
    return rows[0]["sp_aforo_actual"] if rows else 0

def kpis():
    return call_sp("sp_kpis")
