# app/lib/auth.py
import hashlib
import json
import streamlit as st
from .db import query

# -------------------------------------------
# Fallback local (por si aún no migras a tablas RBAC)
# -------------------------------------------
FALLBACK_PERMISSIONS = {
    "kpi_view": {"admin", "recepcion", "entrenador", "finanzas"},
    "users_manage": {"admin"},
    "socios_read": {"admin", "recepcion"},
    "socios_create": {"admin", "recepcion"},
    "socios_update": {"admin", "recepcion"},
    "socios_delete": {"admin"},
    "plans_manage": {"admin"},
    "membership_assign": {"admin", "recepcion"},
    "payments_register": {"admin", "finanzas", "recepcion"},  # si usas 'payments_create', agrega también
    "payments_read": {"admin", "finanzas", "recepcion"},
    "payments_create": {"admin", "finanzas", "recepcion"},
    "payments_refund": {"admin", "finanzas"},
    "classes_publish": {"admin", "entrenador"},
    "classes_edit": {"admin", "entrenador"},
    "classes_delete": {"admin"},
    "reservations_create": {"admin", "recepcion", "entrenador"},
    "checkin": {"admin", "recepcion", "entrenador"},
    "access_entry": {"admin", "recepcion"},
    "access_exit": {"admin", "recepcion"},
    "reports_view": {"admin", "finanzas"},
    "products_manage": {"admin", "finanzas"},
    "sales_create": {"admin", "recepcion"},
    "sales_read": {"admin", "recepcion", "finanzas"},
    "sales_refund": {"admin", "finanzas"},
    "audit_view": {"admin"},
    "all_sedes": {"admin", "gerente"},
}

# -------------------------------------------
# Utilidades internas
# -------------------------------------------
def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def _load_roles_for_user(user_id: int) -> list[str]:
    """Devuelve roles del usuario desde tabla user_role (si existe)."""
    try:
        rows = query("""
            SELECT r.name
            FROM user_role ur
            JOIN role r ON r.id = ur.role_id
            WHERE ur.user_id = %s
            ORDER BY r.name
        """, (user_id,))
        return [r["name"] for r in rows]
    except Exception:
        # si aún no hay tablas RBAC, usa el campo 'rol' de app_user
        u = st.session_state.get("user") or {}
        return [str(u.get("rol") or "").lower()] if u.get("rol") else []

def load_permissions(user_id: int) -> None:
    """
    Carga y cachea permisos efectivos del usuario:
      - Intenta vista v_user_permissions (roles + overrides)
      - Si falla, usa FALLBACK_PERMISSIONS en base al rol de app_user
    """
    try:
        rows = query("SELECT perm FROM v_user_permissions WHERE user_id = %s", (user_id,))
        st.session_state["permissions"] = {r["perm"] for r in rows}
        st.session_state["roles"] = _load_roles_for_user(user_id)
        # Si el usuario es 'admin' por tabla de roles, concede todo por conveniencia:
        if "admin" in st.session_state.get("roles", []):
            # opcional: podrías saltarte esto si ya asignas todo a admin en BD
            pass
    except Exception:
        # Fallback: deriva permisos por el rol simple (campo app_user.rol)
        u = st.session_state.get("user") or {}
        role = str(u.get("rol") or "").lower()
        perms = {p for p, roles in FALLBACK_PERMISSIONS.items() if role in roles or role == "admin"}
        st.session_state["permissions"] = perms
        st.session_state["roles"] = [role] if role else []

def has_permission(perm: str) -> bool:
    """True si el usuario tiene el permiso. Usa cache en session_state."""
    perms = st.session_state.get("permissions")
    if perms is None:
        u = st.session_state.get("user")
        if not u:
            return False
        load_permissions(u["id"])
        perms = st.session_state.get("permissions", set())
    # Superusuario por campo 'rol' (compatibilidad)
    u = st.session_state.get("user") or {}
    if str(u.get("rol")).lower() == "admin":
        return True
    return perm in perms

def has_any(perms_list: list[str]) -> bool:
    return any(has_permission(p) for p in perms_list)

def require_perm(*perms: str):
    """Bloquea si faltan TODOS los permisos requeridos (AND)."""
    require_login()
    missing = [p for p in perms if not has_permission(p)]
    if missing:
        st.error("No tienes permisos para esta acción.")
        st.stop()

def require_any(*perms: str):
    """Bloquea si no tiene NINGUNO de los permisos (OR)."""
    require_login()
    if not any(has_permission(p) for p in perms):
        st.error("No tienes permisos suficientes.")
        st.stop()

def has_role(role_name: str) -> bool:
    roles = st.session_state.get("roles") or []
    return role_name.lower() in [r.lower() for r in roles]

def require_role(*roles):
    require_login()
    if not any(has_role(r) for r in roles):
        st.error("No tienes permisos para esta acción.")
        st.stop()

def logout():
    for k in ("user", "permissions", "roles", "jwt", "auth_user", "session_id", "col_index"):
        st.session_state.pop(k, None)

def on_login_success(user: dict):
    """Guarda usuario y carga permisos efectivos."""
    st.session_state["user"] = user
    load_permissions(user["id"])

# -------------------------------------------
# Login / sesión
# -------------------------------------------
def _db_login(email: str, password: str):
    """
    Valida con pgcrypto/crypt() en la BD (bcrypt). Si no está disponible,
    cae a comparar SHA-256 (compatibilidad con tu implementación previa).
    """
    # 1) Intento con pgcrypto/crypt()
    try:
        rows = query("""
            SELECT id, email, rol, sede_id,
                   (password_hash = crypt(%s, password_hash)) AS ok
            FROM app_user
            WHERE email = %s
            LIMIT 1
        """, (password, email))
        if rows and rows[0].get("ok"):
            return {"id": rows[0]["id"], "email": rows[0]["email"], "rol": rows[0]["rol"], "sede_id": rows[0]["sede_id"]}
        # Si no ok, cae al fallback más abajo
    except Exception:
        # Puede fallar si no existe la extensión pgcrypto o si password_hash tiene otro formato
        pass

    # 2) Fallback a SHA-256 (tu código original)
    try:
        rows = query("SELECT id, email, password_hash, rol, sede_id FROM app_user WHERE email=%s LIMIT 1", (email,))
        if rows and rows[0]["password_hash"] == _sha256(password):
            return {"id": rows[0]["id"], "email": rows[0]["email"], "rol": rows[0]["rol"], "sede_id": rows[0]["sede_id"]}
    except Exception:
        pass

    return None

def login_form():
    st.session_state.setdefault("user", None)
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Ingresar")
    if submit:
        user = _db_login(email.strip(), password)
        if user:
            on_login_success(user)
            st.success("Ingreso correcto")
            st.rerun()
        else:
            st.error("Credenciales inválidas")

def require_login():
    if not st.session_state.get("user"):
        st.info("Inicia sesión para continuar")
        login_form()
        st.stop()

# -------------------------------------------
# Scope por sede (helper útil en listados)
# -------------------------------------------
def add_sede_scope(sql: str, params: list | tuple):
    """
    Si el usuario NO tiene 'all_sedes', agrega filtro por su sede_id.
    Uso:
        sql, params = add_sede_scope(sql, [desde, hasta])
        rows = query(sql, tuple(params))
    """
    u = st.session_state.get("user") or {}
    if has_permission("all_sedes"):
        return sql, params
    sede_id = u.get("sede_id")
    if sede_id is None:
        return sql, params
    # Si el SQL ya tiene WHERE, agrega AND; si no, agrega WHERE.
    glue = " AND " if " where " in sql.lower() else " WHERE "
    sql = f"{sql}{glue}%s = %s"
    # Nota: asume que tus tablas usan columna 'sede_id'; ajusta a tu alias: e.g., "c.sede_id = %s"
    # Para mayor control, puedes pasar aquí la condición exacta; o crea un add_sede_scope_for(alias)
    # Por simplicidad, devolvemos tal cual y el consumidor ajusta si necesita.
    return sql, list(params) + [("sede_id", sede_id)]  # marcador informativo; ajústalo si usas psycopg directo

# -------------------------------------------
# Auditoría (opcional)
# -------------------------------------------
def audit(accion: str, entidad: str, entidad_id=None, detalle: dict | None = None):
    """
    Inserta un registro en auditoria (ignora errores si la tabla no existe).
    """
    try:
        u = st.session_state.get("user") or {}
        uid = u.get("id")
        payload = json.dumps(detalle, ensure_ascii=False) if detalle is not None else None
        query("""
            INSERT INTO auditoria (usuario_id, accion, entidad, entidad_id, detalle)
            VALUES (%s, %s, %s, %s, %s::jsonb)
        """, (uid, accion, entidad, entidad_id, payload))
    except Exception:
        pass
