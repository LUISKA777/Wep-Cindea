-- ============================================================
-- EJECUTAR en Supabase > SQL Editor
-- Actualización: 3 niveles de matrícula con cupos por nivel
-- ============================================================

-- 1. Columnas base de configuración (si no existen)
ALTER TABLE settings
  ADD COLUMN IF NOT EXISTS mat_work_days TEXT DEFAULT '0,1,2,3,4',
  ADD COLUMN IF NOT EXISTS mat_start_time TEXT DEFAULT '08:00',
  ADD COLUMN IF NOT EXISTS mat_end_time TEXT DEFAULT '16:00',
  ADD COLUMN IF NOT EXISTS mat_lunch_start TEXT DEFAULT '12:00',
  ADD COLUMN IF NOT EXISTS mat_lunch_end TEXT DEFAULT '13:00',
  ADD COLUMN IF NOT EXISTS mat_apt_duration TEXT DEFAULT '30';

-- 2. Columnas para Primer Nivel (Primaria)
ALTER TABLE settings
  ADD COLUMN IF NOT EXISTS mat_primaria_opening DATE,
  ADD COLUMN IF NOT EXISTS mat_primaria_closing DATE,
  ADD COLUMN IF NOT EXISTS mat_primaria_cupos INTEGER;

-- 3. Columnas para Segundo Nivel (7°, 8° y 9°)
ALTER TABLE settings
  ADD COLUMN IF NOT EXISTS mat_segundo_nivel_opening DATE,
  ADD COLUMN IF NOT EXISTS mat_segundo_nivel_closing DATE,
  ADD COLUMN IF NOT EXISTS mat_segundo_nivel_cupos INTEGER;

-- 4. Columnas para Tercer Nivel Diversificado (10° y 11°)
ALTER TABLE settings
  ADD COLUMN IF NOT EXISTS mat_tercer_nivel_opening DATE,
  ADD COLUMN IF NOT EXISTS mat_tercer_nivel_closing DATE,
  ADD COLUMN IF NOT EXISTS mat_tercer_nivel_cupos INTEGER;

-- 5. Tabla de citas de matrícula (actualizada con nuevos ciclos)
CREATE TABLE IF NOT EXISTS matricula_appointments (
  id SERIAL PRIMARY KEY,
  student_name TEXT NOT NULL,
  student_cedula TEXT NOT NULL,
  student_phone TEXT NOT NULL,
  cycle TEXT NOT NULL,  -- 'primaria', 'segundo_nivel', 'tercer_nivel'
  appointment_date DATE NOT NULL,
  appointment_time TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Nota: si ya tenías la tabla con cycle='secundaria', puedes migrar así:
-- UPDATE matricula_appointments SET cycle = 'segundo_nivel' WHERE cycle = 'secundaria';

-- Listo. Guarde la configuración de matrícula desde el panel admin.
