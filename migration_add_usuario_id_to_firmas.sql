-- =============================================
-- Migration: Add usuario_id to firmas table
-- Run in Supabase SQL Editor
-- =============================================

BEGIN;

-- =============================================
-- 1. Add usuario_id column to firmas
-- =============================================

ALTER TABLE firmas ADD COLUMN IF NOT EXISTS usuario_id VARCHAR(36);
ALTER TABLE firmas ADD FOREIGN KEY (usuario_id) REFERENCES usuarios(id);

CREATE INDEX IF NOT EXISTS idx_firmas_usuario_id ON firmas(usuario_id);

-- =============================================
-- 2. Update existing records (extract from nombre)
-- The nombre format is "usuario_<UUID>" or "usuario_<UUID>_<timestamp>"
-- We extract the UUID part after "usuario_"
-- =============================================

UPDATE firmas
SET usuario_id = SUBSTRING(nombre FROM 9 FOR 36)
WHERE nombre LIKE 'usuario_%'
AND usuario_id IS NULL
AND LENGTH(SUBSTRING(nombre FROM 9 FOR 36)) = 36;

-- =============================================
-- 3. Drop old RLS policies for firmas
-- =============================================

DROP POLICY IF EXISTS "firmas_read" ON firmas;
DROP POLICY IF EXISTS "firmas_insert" ON firmas;
DROP POLICY IF EXISTS "firmas_update" ON firmas;
DROP POLICY IF EXISTS "firmas_delete" ON firmas;

-- =============================================
-- 4. Create new RLS policies with usuario_id
-- =============================================

CREATE POLICY "firmas_read_own" ON firmas
    FOR SELECT USING (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "firmas_insert_own" ON firmas
    FOR INSERT WITH CHECK (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "firmas_update_own" ON firmas
    FOR UPDATE USING (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "firmas_delete_own" ON firmas
    FOR DELETE USING (usuario_id::text = current_setting('app.current_user_id', true));

COMMIT;

-- =============================================
-- Verify
-- =============================================

SELECT
    column_name,
    data_type,
    is_nullable
FROM information_schema.columns
WHERE table_name = 'firmas'
AND column_name IN ('id', 'nombre', 'usuario_id')
ORDER BY column_name;