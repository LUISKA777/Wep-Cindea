-- ============================================================
-- SUPABASE MIGRATION FOR HORARIOS (SCHEDULES)
-- ============================================================

-- 1. Add columns for horarios configuration to settings table
ALTER TABLE settings
  ADD COLUMN IF NOT EXISTS hor_primera_apertura DATE,
  ADD COLUMN IF NOT EXISTS hor_primera_cierre DATE,
  ADD COLUMN IF NOT EXISTS hor_segunda_apertura DATE,
  ADD COLUMN IF NOT EXISTS hor_segunda_cierre DATE,
  ADD COLUMN IF NOT EXISTS hor_tercera_apertura DATE,
  ADD COLUMN IF NOT EXISTS hor_tercera_cierre DATE;

-- 2. Create table for horarios (schedules)
CREATE TABLE IF NOT EXISTS horarios (
  id SERIAL PRIMARY KEY,
  level TEXT NOT NULL CHECK (level IN ('primer_nivel', 'segundo_nivel', 'tercer_nivel')),
  name TEXT NOT NULL,
  photo_url TEXT,
  description TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Add index for better performance on level queries
CREATE INDEX IF NOT EXISTS idx_horarios_level ON horarios(level);

-- ============================================================
-- INSTRUCCIONES:
-- 1. Ejecutar este SQL en el editor SQL de Supabase
-- 2. Actualizar app.py con los cambios para horarios
-- 3. Crear las nuevas plantillas
-- ============================================================