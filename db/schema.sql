CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Sedes
CREATE TABLE IF NOT EXISTS sede (
  id BIGSERIAL PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE
);

-- Usuarios (para login y roles)
CREATE TABLE IF NOT EXISTS app_user (
  id BIGSERIAL PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  rol TEXT NOT NULL DEFAULT 'admin', -- admin, recepcion, entrenador, finanzas
  sede_id BIGINT REFERENCES sede(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Socios
CREATE TABLE IF NOT EXISTS socio (
  id BIGSERIAL PRIMARY KEY,
  dni TEXT,
  nombre TEXT NOT NULL,
  email TEXT,
  telefono TEXT,
  fecha_alta DATE DEFAULT CURRENT_DATE,
  estado TEXT NOT NULL DEFAULT 'activo', -- activo, inactivo
  foto_url TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_socio_dni ON socio(dni) WHERE dni IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS ux_socio_email ON socio(email) WHERE email IS NOT NULL;

-- Planes de membresía
CREATE TABLE IF NOT EXISTS membresia_plan (
  id BIGSERIAL PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE,
  precio_mensual NUMERIC(10,2) NOT NULL DEFAULT 0,
  duracion_dias INT NOT NULL DEFAULT 30,
  max_congelamiento INT NOT NULL DEFAULT 30
);

-- Membresías
CREATE TABLE IF NOT EXISTS membresia (
  id BIGSERIAL PRIMARY KEY,
  socio_id BIGINT NOT NULL REFERENCES socio(id) ON DELETE CASCADE,
  plan_id BIGINT NOT NULL REFERENCES membresia_plan(id),
  fecha_inicio DATE NOT NULL,
  fecha_fin DATE NOT NULL,
  estado TEXT NOT NULL DEFAULT 'activa' -- activa, vencida, congelada, cancelada
);
CREATE INDEX IF NOT EXISTS ix_membresia_socio ON membresia(socio_id);
CREATE INDEX IF NOT EXISTS ix_membresia_estado ON membresia(estado);

-- Pagos
CREATE TABLE IF NOT EXISTS pago (
  id BIGSERIAL PRIMARY KEY,
  socio_id BIGINT NOT NULL REFERENCES socio(id) ON DELETE CASCADE,
  concepto TEXT NOT NULL,
  monto NUMERIC(10,2) NOT NULL,
  medio TEXT NOT NULL, -- efectivo, tarjeta, transferencia
  ref_externa TEXT,
  fecha TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_pago_socio ON pago(socio_id);
CREATE INDEX IF NOT EXISTS ix_pago_fecha ON pago(fecha);

-- Clases
CREATE TABLE IF NOT EXISTS clase (
  id BIGSERIAL PRIMARY KEY,
  sede_id BIGINT NOT NULL REFERENCES sede(id) ON DELETE CASCADE,
  nombre TEXT NOT NULL,
  fecha_hora TIMESTAMPTZ NOT NULL,
  capacidad INT NOT NULL DEFAULT 10,
  estado TEXT NOT NULL DEFAULT 'programada' -- programada, cancelada, realizada
);
CREATE INDEX IF NOT EXISTS ix_clase_fecha ON clase(fecha_hora);

-- Reservas
CREATE TABLE IF NOT EXISTS reserva (
  id BIGSERIAL PRIMARY KEY,
  clase_id BIGINT NOT NULL REFERENCES clase(id) ON DELETE CASCADE,
  socio_id BIGINT NOT NULL REFERENCES socio(id) ON DELETE CASCADE,
  estado TEXT NOT NULL DEFAULT 'confirmada', -- confirmada, cancelada, waitlist
  fecha_reserva TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (clase_id, socio_id)
);
CREATE INDEX IF NOT EXISTS ix_reserva_estado ON reserva(estado);

-- Accesos (aforo)
CREATE TABLE IF NOT EXISTS acceso (
  id BIGSERIAL PRIMARY KEY,
  socio_id BIGINT NOT NULL REFERENCES socio(id) ON DELETE CASCADE,
  sede_id BIGINT NOT NULL REFERENCES sede(id) ON DELETE CASCADE,
  fecha_entrada TIMESTAMPTZ NOT NULL DEFAULT now(),
  fecha_salida TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS ix_acceso_sede ON acceso(sede_id);
CREATE INDEX IF NOT EXISTS ix_acceso_abiertos ON acceso(sede_id, fecha_salida);

-- Productos / Ventas (simplificado)
CREATE TABLE IF NOT EXISTS producto (
  id BIGSERIAL PRIMARY KEY,
  nombre TEXT NOT NULL UNIQUE,
  precio NUMERIC(10,2) NOT NULL,
  stock INT NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS venta (
  id BIGSERIAL PRIMARY KEY,
  socio_id BIGINT REFERENCES socio(id) ON DELETE SET NULL,
  fecha TIMESTAMPTZ NOT NULL DEFAULT now(),
  total NUMERIC(10,2) NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS venta_item (
  id BIGSERIAL PRIMARY KEY,
  venta_id BIGINT NOT NULL REFERENCES venta(id) ON DELETE CASCADE,
  producto_id BIGINT NOT NULL REFERENCES producto(id),
  cantidad INT NOT NULL,
  precio NUMERIC(10,2) NOT NULL
);

-- Auditoría sencilla
CREATE TABLE IF NOT EXISTS auditoria (
  id BIGSERIAL PRIMARY KEY,
  usuario_id BIGINT REFERENCES app_user(id) ON DELETE SET NULL,
  accion TEXT NOT NULL,
  entidad TEXT NOT NULL,
  entidad_id BIGINT,
  detalle JSONB,
  ts TIMESTAMPTZ NOT NULL DEFAULT now()
);
