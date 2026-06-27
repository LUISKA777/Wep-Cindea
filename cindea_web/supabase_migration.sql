-- ============================================================
-- EJECUTAR en Supabase > SQL Editor
-- Tres niveles de matrícula con cupos — columnas TEXT para cupos
-- ============================================================

-- 1. Columnas de horario (si no existen)
ALTER TABLE settings
  ADD COLUMN IF NOT EXISTS mat_work_days TEXT DEFAULT '0,1,2,3,4',
  ADD COLUMN IF NOT EXISTS mat_start_time TEXT DEFAULT '08:00',
  ADD COLUMN IF NOT EXISTS mat_end_time TEXT DEFAULT '16:00',
  ADD COLUMN IF NOT EXISTS mat_lunch_start TEXT DEFAULT '12:00',
  ADD COLUMN IF NOT EXISTS mat_lunch_end TEXT DEFAULT '13:00',
  ADD COLUMN IF NOT EXISTS mat_apt_duration TEXT DEFAULT '30';

-- 2. Primer Nivel (Primaria)
ALTER TABLE settings
  ADD COLUMN IF NOT EXISTS mat_primaria_opening DATE,
  ADD COLUMN IF NOT EXISTS mat_primaria_closing DATE,
  ADD COLUMN IF NOT EXISTS mat_primaria_cupos TEXT DEFAULT '';

-- 3. Segundo Nivel (7°, 8° y 9°)
ALTER TABLE settings
  ADD COLUMN IF NOT EXISTS mat_segundo_nivel_opening DATE,
  ADD COLUMN IF NOT EXISTS mat_segundo_nivel_closing DATE,
  ADD COLUMN IF NOT EXISTS mat_segundo_nivel_cupos TEXT DEFAULT '';

-- 4. Tercer Nivel Diversificado (10° y 11°)
ALTER TABLE settings
  ADD COLUMN IF NOT EXISTS mat_tercer_nivel_opening DATE,
  ADD COLUMN IF NOT EXISTS mat_tercer_nivel_closing DATE,
  ADD COLUMN IF NOT EXISTS mat_tercer_nivel_cupos TEXT DEFAULT '';

-- 5. Tabla de citas de matrícula
CREATE TABLE IF NOT EXISTS matricula_appointments (
  id SERIAL PRIMARY KEY,
  student_name TEXT NOT NULL,
  student_cedula TEXT NOT NULL,
  student_phone TEXT NOT NULL,
  cycle TEXT NOT NULL,   -- 'primaria', 'segundo_nivel', 'tercer_nivel'
  appointment_date DATE NOT NULL,
  appointment_time TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Si tenía citas antiguas con cycle='secundaria', puede migrarlas:
-- UPDATE matricula_appointments SET cycle = 'segundo_nivel' WHERE cycle = 'secundaria';

-- NOTA sobre "Tracking Prevention blocked":
-- Ese mensaje es del navegador (Safari/Edge bloqueando cookies de terceros).
-- Para resolverlo en producción, configure su dominio con cookies SameSite=None; Secure
-- o use un dominio propio en Vercel.

-- ============================================================
-- NUEVAS COLUMNAS — Ejecutar si se actualizó app.py v2
-- ============================================================

-- 6. Horarios individuales por nivel de matrícula
ALTER TABLE settings
  ADD COLUMN IF NOT EXISTS mat_primaria_work_days TEXT,
  ADD COLUMN IF NOT EXISTS mat_primaria_start_time TEXT,
  ADD COLUMN IF NOT EXISTS mat_primaria_end_time TEXT,
  ADD COLUMN IF NOT EXISTS mat_primaria_apt_duration TEXT,
  ADD COLUMN IF NOT EXISTS mat_segundo_nivel_work_days TEXT,
  ADD COLUMN IF NOT EXISTS mat_segundo_nivel_start_time TEXT,
  ADD COLUMN IF NOT EXISTS mat_segundo_nivel_end_time TEXT,
  ADD COLUMN IF NOT EXISTS mat_segundo_nivel_apt_duration TEXT,
  ADD COLUMN IF NOT EXISTS mat_tercer_nivel_work_days TEXT,
  ADD COLUMN IF NOT EXISTS mat_tercer_nivel_start_time TEXT,
  ADD COLUMN IF NOT EXISTS mat_tercer_nivel_end_time TEXT,
  ADD COLUMN IF NOT EXISTS mat_tercer_nivel_apt_duration TEXT;

-- 7. Columna hidden en courses para ocultar de la web sin borrar
ALTER TABLE courses
  ADD COLUMN IF NOT EXISTS hidden BOOLEAN DEFAULT FALSE;
