
INSERT INTO sede(nombre) VALUES ('Central') ON CONFLICT DO NOTHING;
INSERT INTO sede(nombre) VALUES ('Norte') ON CONFLICT DO NOTHING;

-- Usuario admin (password: admin123)
INSERT INTO app_user(email, password_hash, rol, sede_id)
SELECT 'admin@gym.local', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', 'admin', (SELECT id FROM sede LIMIT 1)
WHERE NOT EXISTS (SELECT 1 FROM app_user WHERE email='admin@gym.local');

-- Planes base
INSERT INTO membresia_plan(nombre, precio_mensual, duracion_dias, max_congelamiento) VALUES
 ('Mensual', 120.00, 30, 30) ON CONFLICT DO NOTHING;
INSERT INTO membresia_plan(nombre, precio_mensual, duracion_dias, max_congelamiento) VALUES
 ('Trimestral', 300.00, 90, 45) ON CONFLICT DO NOTHING;

-- Datos de ejemplo
WITH s AS (
  INSERT INTO socio(dni, nombre, email, telefono)
  VALUES ('70000001','Ana Perez','ana@example.com','999111222')
  ON CONFLICT DO NOTHING RETURNING id
)
INSERT INTO membresia(socio_id, plan_id, fecha_inicio, fecha_fin, estado)
SELECT (SELECT id FROM socio WHERE email='ana@example.com'),
       (SELECT id FROM membresia_plan WHERE nombre='Mensual'),
       CURRENT_DATE, CURRENT_DATE + INTERVAL '30 days', 'activa'
WHERE NOT EXISTS (
  SELECT 1 FROM membresia WHERE socio_id=(SELECT id FROM socio WHERE email='ana@example.com')
);
