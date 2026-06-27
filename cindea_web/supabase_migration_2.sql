-- ============================================================
-- SUPABASE MIGRATION FOR ROLE-BASED ACCESS AND ACADEMIC TRACKING
-- ============================================================

-- 1. Extend users table with role and profile fields
ALTER TABLE users
  ADD COLUMN IF NOT EXISTS role VARCHAR(20) DEFAULT 'student',
  ADD COLUMN IF NOT EXISTS first_name VARCHAR(100),
  ADD COLUMN IF NOT EXISTS last_name VARCHAR(100),
  ADD COLUMN IF NOT EXISTS cedula VARCHAR(20),
  ADD COLUMN IF NOT EXISTS email VARCHAR(255),
  ADD COLUMN IF NOT EXISTS phone VARCHAR(20),
  ADD COLUMN IF NOT EXISTS level VARCHAR(20);  -- For students: primaria, segundo_nivel, tercer_nivel

-- 2. Create subjects table (materias)
CREATE TABLE IF NOT EXISTS subjects (
  id SERIAL PRIMARY KEY,
  name VARCHAR(200) NOT NULL,
  code VARCHAR(50) UNIQUE,
  level VARCHAR(20) NOT NULL,  -- primaria, segundo_nivel, tercer_nivel
  grade_level VARCHAR(50),     -- e.g., "1ero", "2do", etc.
  credits INTEGER DEFAULT 1,
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Create student_subjects table (enrollments)
CREATE TABLE IF NOT EXISTS student_subjects (
  id SERIAL PRIMARY KEY,
  student_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
  subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
  enrollment_date DATE DEFAULT CURRENT_DATE,
  is_active BOOLEAN DEFAULT TRUE,
  UNIQUE(student_id, subject_id)
);

-- 4. Create grades table
CREATE TABLE IF NOT EXISTS grades (
  id SERIAL PRIMARY KEY,
  student_subject_id INTEGER REFERENCES student_subjects(id) ON DELETE CASCADE,
  final_grade DECIMAL(5,2),
  passed BOOLEAN GENERATED ALWAYS AS (
    CASE
      WHEN final_grade IS NULL THEN FALSE
      WHEN (
        SELECT u.level FROM users u
        JOIN student_subjects ss ON u.id = ss.student_id
        WHERE ss.id = student_subject_id
      ) IN ('primaria', 'segundo_nivel') AND final_grade >= 65 THEN TRUE
      WHEN (
        SELECT u.level FROM users u
        JOIN student_subjects ss ON u.id = ss.student_id
        WHERE ss.id = student_subject_id
      ) = 'tercer_nivel' AND final_grade >= 70 THEN TRUE
      ELSE FALSE
    END
  ) STORED,
  graded_at TIMESTAMPTZ DEFAULT NOW(),
  graded_by INTEGER REFERENCES users(id)  -- Professor who entered the grade
);

-- 5. Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_cedula ON users(cedula);
CREATE INDEX IF NOT EXISTS idx_student_subjects_student ON student_subjects(student_id);
CREATE INDEX IF NOT EXISTS idx_grades_student_subject ON grades(student_subject_id);

-- ============================================================
-- INSTRUCCIONES:
-- 1. Ejecutar este SQL en el editor SQL de Supabase
-- 2. Actualizar requirements.txt para incluir werkzeug
-- 3. Actualizar app.py con los cambios de autenticación
-- 4. Crear las nuevas plantillas
-- ============================================================