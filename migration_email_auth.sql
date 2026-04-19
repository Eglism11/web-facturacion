-- Migration: Rename username to email in usuarios table
-- Run in Supabase SQL Editor
-- =============================================

BEGIN;

-- =============================================
-- 1. Rename username column to email
-- =============================================

ALTER TABLE usuarios RENAME COLUMN username TO email;

-- =============================================
-- 2. Add unique constraint on email (if not exists)
-- =============================================

ALTER TABLE usuarios ADD CONSTRAINT uq_usuarios_email UNIQUE (email);

COMMIT;

-- =============================================
-- Verify
-- =============================================

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_name = 'usuarios'
AND column_name IN ('id', 'email')
ORDER BY column_name;