-- ============================================================
-- EJECUTAR en Supabase > SQL Editor
-- Agrega columnas de configuración de matrícula a la tabla settings
-- y crea la tabla matricula_appointments
-- ============================================================

-- 1. Nuevas columnas en tabla settings
ALTER TABLE settings
  ADD COLUMN IF NOT EXISTS mat_work_days TEXT DEFAULT '0,1,2,3,4',
  ADD COLUMN IF NOT EXISTS mat_start_time TEXT DEFAULT '08:00',
  ADD COLUMN IF NOT EXISTS mat_end_time TEXT DEFAULT '16:00',
  ADD COLUMN IF NOT EXISTS mat_lunch_start TEXT DEFAULT '12:00',
  ADD COLUMN IF NOT EXISTS mat_lunch_end TEXT DEFAULT '13:00',
  ADD COLUMN IF NOT EXISTS mat_apt_duration TEXT DEFAULT '30',
  ADD COLUMN IF NOT EXISTS mat_primaria_opening DATE,
  ADD COLUMN IF NOT EXISTS mat_primaria_closing DATE,
  ADD COLUMN IF NOT EXISTS mat_secundaria_opening DATE,
  ADD COLUMN IF NOT EXISTS mat_secundaria_closing DATE;

-- 2. Tabla de citas de matrícula (si no existe)
CREATE TABLE IF NOT EXISTS matricula_appointments (
  id SERIAL PRIMARY KEY,
  student_name TEXT NOT NULL,
  student_cedula TEXT NOT NULL,
  student_phone TEXT NOT NULL,
  cycle TEXT NOT NULL,       -- 'primaria' o 'secundaria'
  appointment_date DATE NOT NULL,
  appointment_time TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Listo. Ya puede guardar configuración de matrícula desde el panel admin.
