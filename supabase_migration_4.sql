-- ============================================================
-- SUPABASE MIGRATION FOR SECTION ASSIGNMENTS
-- Permite al superadmin:
--   1) Definir secciones por nivel (ej. "7-A", "7-B", "10-A")
--   2) Cargar un Excel con nombre, cedula, seccion (upsert por cedula)
--   3) Imprimir la lista agrupada por seccion
-- Los estudiantes consultan su seccion por cedula en /secciones
-- ============================================================

-- 1. Tabla de secciones predefinidas por nivel
CREATE TABLE IF NOT EXISTS sections (
  id SERIAL PRIMARY KEY,
  level TEXT NOT NULL CHECK (level IN ('primaria', 'segundo_nivel', 'tercer_nivel')),
  name TEXT NOT NULL,
  display_order INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(level, name)
);

-- 2. Tabla de asignaciones (un registro activo por cedula)
CREATE TABLE IF NOT EXISTS section_assignments (
  id SERIAL PRIMARY KEY,
  student_cedula TEXT NOT NULL,
  student_name TEXT NOT NULL,
  section_id INTEGER REFERENCES sections(id) ON DELETE SET NULL,
  level TEXT NOT NULL CHECK (level IN ('primaria', 'segundo_nivel', 'tercer_nivel')),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE(student_cedula)
);

-- 3. Indices para consultas rapidas
CREATE INDEX IF NOT EXISTS idx_sections_level ON sections(level);
CREATE INDEX IF NOT EXISTS idx_section_assignments_cedula ON section_assignments(student_cedula);
CREATE INDEX IF NOT EXISTS idx_section_assignments_section_id ON section_assignments(section_id);
CREATE INDEX IF NOT EXISTS idx_section_assignments_level ON section_assignments(level);

-- 4. Trigger: actualizar updated_at automaticamente en updates
CREATE OR REPLACE FUNCTION trg_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_section_assignments_updated_at ON section_assignments;
CREATE TRIGGER set_section_assignments_updated_at
  BEFORE UPDATE ON section_assignments
  FOR EACH ROW
  EXECUTE FUNCTION trg_set_updated_at();

-- ============================================================
-- INSTRUCCIONES:
-- 1. Ejecutar este SQL en el editor SQL de Supabase
-- 2. Reiniciar la app Flask
-- 3. Entrar como superadmin -> Panel -> "Asignacion de Secciones"
-- 4. Crear las secciones y subir el Excel de estudiantes
-- ============================================================
