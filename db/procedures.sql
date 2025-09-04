-- ===== Procedimientos almacenados (PL/pgSQL) =====

-- Alta de socio con deduplicación básica
CREATE OR REPLACE FUNCTION sp_alta_socio(p_dni TEXT, p_nombre TEXT, p_email TEXT, p_telefono TEXT)
RETURNS TABLE(status TEXT, code INT, message TEXT, socio_id BIGINT) AS $$
DECLARE v_id BIGINT;
BEGIN
  IF p_dni IS NOT NULL AND EXISTS (SELECT 1 FROM socio WHERE dni = p_dni) THEN
    status := 'ERROR'; code := 409; message := 'DNI ya registrado'; socio_id := NULL; RETURN;
  END IF;
  IF p_email IS NOT NULL AND EXISTS (SELECT 1 FROM socio WHERE email = p_email) THEN
    status := 'ERROR'; code := 409; message := 'Email ya registrado'; socio_id := NULL; RETURN;
  END IF;
  INSERT INTO socio(dni, nombre, email, telefono)
  VALUES (NULLIF(p_dni,''), p_nombre, NULLIF(p_email,''), NULLIF(p_telefono,''))
  RETURNING id INTO v_id;
  status := 'OK'; code := 0; message := 'Socio creado'; socio_id := v_id; RETURN;
END;
$$ LANGUAGE plpgsql;

-- Crear membresía (calcula fecha_fin por plan)
CREATE OR REPLACE FUNCTION sp_crear_membresia(p_socio_id BIGINT, p_plan_id BIGINT, p_fecha_inicio DATE)
RETURNS TABLE(status TEXT, code INT, message TEXT, membresia_id BIGINT) AS $$
DECLARE v_dias INT; v_id BIGINT;
BEGIN
  SELECT duracion_dias INTO v_dias FROM membresia_plan WHERE id = p_plan_id;
  IF v_dias IS NULL THEN
    status := 'ERROR'; code := 404; message := 'Plan no existe'; membresia_id := NULL; RETURN;
  END IF;
  INSERT INTO membresia(socio_id, plan_id, fecha_inicio, fecha_fin, estado)
  VALUES (p_socio_id, p_plan_id, p_fecha_inicio, p_fecha_inicio + (v_dias || ' days')::interval, 'activa')
  RETURNING id INTO v_id;
  status := 'OK'; code := 0; message := 'Membresía creada'; membresia_id := v_id; RETURN;
END;
$$ LANGUAGE plpgsql;

-- Registrar pago
CREATE OR REPLACE FUNCTION sp_registrar_pago(p_socio_id BIGINT, p_concepto TEXT, p_monto NUMERIC, p_medio TEXT, p_ref TEXT)
RETURNS TABLE(status TEXT, code INT, message TEXT, pago_id BIGINT) AS $$
DECLARE v_id BIGINT;
BEGIN
  INSERT INTO pago(socio_id, concepto, monto, medio, ref_externa)
  VALUES (p_socio_id, p_concepto, p_monto, p_medio, p_ref)
  RETURNING id INTO v_id;
  status := 'OK'; code := 0; message := 'Pago registrado'; pago_id := v_id; RETURN;
END;
$$ LANGUAGE plpgsql;

-- Publicar clase
CREATE OR REPLACE FUNCTION sp_publicar_clase(p_sede_id BIGINT, p_nombre TEXT, p_fecha_hora TIMESTAMPTZ, p_capacidad INT)
RETURNS TABLE(status TEXT, code INT, message TEXT, clase_id BIGINT) AS $$
DECLARE v_id BIGINT;
BEGIN
  INSERT INTO clase(sede_id, nombre, fecha_hora, capacidad, estado)
  VALUES (p_sede_id, p_nombre, p_fecha_hora, COALESCE(p_capacidad,10), 'programada')
  RETURNING id INTO v_id;
  status := 'OK'; code := 0; message := 'Clase creada'; clase_id := v_id; RETURN;
END;
$$ LANGUAGE plpgsql;

-- Reservar clase (valida capacidad)
CREATE OR REPLACE FUNCTION sp_reservar_clase(p_socio_id BIGINT, p_clase_id BIGINT)
RETURNS TABLE(status TEXT, code INT, message TEXT, reserva_id BIGINT) AS $$
DECLARE v_cap INT; v_tomadas INT; v_id BIGINT;
BEGIN
  SELECT capacidad INTO v_cap FROM clase WHERE id = p_clase_id AND estado='programada';
  IF v_cap IS NULL THEN
    status := 'ERROR'; code := 404; message := 'Clase no disponible'; reserva_id := NULL; RETURN;
  END IF;
  SELECT COUNT(*) INTO v_tomadas FROM reserva WHERE clase_id = p_clase_id AND estado='confirmada';
  IF v_tomadas >= v_cap THEN
    status := 'ERROR'; code := 409; message := 'Cupo lleno'; reserva_id := NULL; RETURN;
  END IF;
  INSERT INTO reserva(clase_id, socio_id, estado) VALUES (p_clase_id, p_socio_id, 'confirmada')
  RETURNING id INTO v_id;
  status := 'OK'; code := 0; message := 'Reserva confirmada'; reserva_id := v_id; RETURN;
END;
$$ LANGUAGE plpgsql;

-- Check-in de clase (marca asistencia simple cambiando estado de reserva)
CREATE OR REPLACE FUNCTION sp_checkin_clase(p_reserva_id BIGINT)
RETURNS TABLE(status TEXT, code INT, message TEXT) AS $$
BEGIN
  UPDATE reserva SET estado='asistio' WHERE id = p_reserva_id AND estado='confirmada';
  IF NOT FOUND THEN
    status := 'ERROR'; code := 404; message := 'Reserva no válida'; RETURN;
  END IF;
  status := 'OK'; code := 0; message := 'Asistencia registrada'; RETURN;
END;
$$ LANGUAGE plpgsql;

-- Registrar acceso (aforo)
CREATE OR REPLACE FUNCTION sp_registrar_acceso(p_socio_id BIGINT, p_sede_id BIGINT)
RETURNS TABLE(status TEXT, code INT, message TEXT, acceso_id BIGINT) AS $$
DECLARE v_activo INT; v_id BIGINT;
BEGIN
  SELECT COUNT(*) INTO v_activo FROM membresia
    WHERE socio_id = p_socio_id AND estado='activa' AND fecha_fin >= CURRENT_DATE;
  IF v_activo = 0 THEN
    status := 'ERROR'; code := 403; message := 'Membresía no activa'; acceso_id := NULL; RETURN;
  END IF;
  INSERT INTO acceso(socio_id, sede_id) VALUES (p_socio_id, p_sede_id) RETURNING id INTO v_id;
  status := 'OK'; code := 0; message := 'Acceso registrado'; acceso_id := v_id; RETURN;
END;
$$ LANGUAGE plpgsql;

-- Registrar salida
CREATE OR REPLACE FUNCTION sp_registrar_salida(p_acceso_id BIGINT)
RETURNS TABLE(status TEXT, code INT, message TEXT) AS $$
BEGIN
  UPDATE acceso SET fecha_salida = now() WHERE id = p_acceso_id AND fecha_salida IS NULL;
  IF NOT FOUND THEN
    status := 'ERROR'; code := 404; message := 'Acceso no encontrado/ya cerrado'; RETURN;
  END IF;
  status := 'OK'; code := 0; message := 'Salida registrada'; RETURN;
END;
$$ LANGUAGE plpgsql;

-- Aforo actual por sede
CREATE OR REPLACE FUNCTION sp_aforo_actual(p_sede_id BIGINT)
RETURNS INT AS $$
DECLARE v_aforo INT;
BEGIN
  SELECT COUNT(*) INTO v_aforo FROM acceso WHERE sede_id = p_sede_id AND fecha_salida IS NULL;
  RETURN v_aforo;
END;
$$ LANGUAGE plpgsql;

-- KPIs simples (socios, membresías activas, accesos hoy)
CREATE OR REPLACE FUNCTION sp_kpis()
RETURNS TABLE(socios INT, membresias_activas INT, accesos_hoy INT) AS $$
BEGIN
  socios := (SELECT COUNT(*) FROM socio);
  membresias_activas := (SELECT COUNT(*) FROM membresia WHERE estado='activa' AND fecha_fin >= CURRENT_DATE);
  accesos_hoy := (SELECT COUNT(*) FROM acceso WHERE fecha_entrada::date = CURRENT_DATE);
  RETURN NEXT;
END;
$$ LANGUAGE plpgsql;
