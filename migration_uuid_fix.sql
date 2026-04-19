-- =============================================
-- Migration: Convert INTEGER user IDs to STRING (UUID compatibility)
-- Safer approach: DROP + ADD to avoid RLS/policy conflicts
-- Run in Supabase SQL Editor
-- =============================================

BEGIN;

-- =============================================
-- 1. USUARIOS TABLE
-- =============================================

-- Drop dependent objects on usuarios.id
DROP POLICY IF EXISTS "users_read_own" ON usuarios;
DROP POLICY IF EXISTS "users_update_own" ON usuarios;
DROP POLICY IF EXISTS "users_insert" ON usuarios;
DROP POLICY IF EXISTS "users_delete_own" ON usuarios;

-- Add new column
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS id_new VARCHAR(36);

-- Copy data (convert integer to string)
UPDATE usuarios SET id_new = CAST(id AS VARCHAR(36));

-- Drop old column and rename
ALTER TABLE usuarios DROP COLUMN id;
ALTER TABLE usuarios ALTER COLUMN id_new RENAME TO id;

-- Set primary key again
ALTER TABLE usuarios ADD PRIMARY KEY (id);

-- Recreate policies
CREATE POLICY "users_read_own" ON usuarios FOR SELECT USING (true);
CREATE POLICY "users_update_own" ON usuarios FOR UPDATE USING (true);
CREATE POLICY "users_insert" ON usuarios FOR INSERT WITH CHECK (true);
CREATE POLICY "users_delete_own" ON usuarios FOR DELETE USING (true);

-- =============================================
-- 2. CLIENTES TABLE
-- =============================================

-- Drop dependent objects
DROP POLICY IF EXISTS "clientes_read_own" ON clientes;
DROP POLICY IF EXISTS "clientes_insert_own" ON clientes;
DROP POLICY IF EXISTS "clientes_update_own" ON clientes;
DROP POLICY IF EXISTS "clientes_delete_own" ON clientes;

-- Add new column
ALTER TABLE clientes ADD COLUMN IF NOT EXISTS usuario_id_new VARCHAR(36);

-- Copy data
UPDATE clientes SET usuario_id_new = CAST(usuario_id AS VARCHAR(36));

-- Drop old column and rename
ALTER TABLE clientes DROP COLUMN usuario_id;
ALTER TABLE clientes ALTER COLUMN usuario_id_new RENAME TO usuario_id;

-- Recreate policies and constraints
ALTER TABLE clientes ADD FOREIGN KEY (usuario_id) REFERENCES usuarios(id);

CREATE POLICY "clientes_read_own" ON clientes FOR SELECT USING (true);
CREATE POLICY "clientes_insert_own" ON clientes FOR INSERT WITH CHECK (true);
CREATE POLICY "clientes_update_own" ON clientes FOR UPDATE USING (true);
CREATE POLICY "clientes_delete_own" ON clientes FOR DELETE USING (true);

-- =============================================
-- 3. CUENTAS TABLE
-- =============================================

DROP POLICY IF EXISTS "cuentas_read_own" ON cuentas;
DROP POLICY IF EXISTS "cuentas_insert_own" ON cuentas;
DROP POLICY IF EXISTS "cuentas_update_own" ON cuentas;
DROP POLICY IF EXISTS "cuentas_delete_own" ON cuentas;

ALTER TABLE cuentas ADD COLUMN IF NOT EXISTS usuario_id_new VARCHAR(36);
UPDATE cuentas SET usuario_id_new = CAST(usuario_id AS VARCHAR(36));
ALTER TABLE cuentas DROP COLUMN usuario_id;
ALTER TABLE cuentas ALTER COLUMN usuario_id_new RENAME TO usuario_id;

ALTER TABLE cuentas ADD FOREIGN KEY (usuario_id) REFERENCES usuarios(id);

CREATE POLICY "cuentas_read_own" ON cuentas FOR SELECT USING (true);
CREATE POLICY "cuentas_insert_own" ON cuentas FOR INSERT WITH CHECK (true);
CREATE POLICY "cuentas_update_own" ON cuentas FOR UPDATE USING (true);
CREATE POLICY "cuentas_delete_own" ON cuentas FOR DELETE USING (true);

-- =============================================
-- 4. CUENTAS_BANCARIAS TABLE
-- =============================================

DROP POLICY IF EXISTS "cuentas_bancarias_read_own" ON cuentas_bancarias;
DROP POLICY IF EXISTS "cuentas_bancarias_insert_own" ON cuentas_bancarias;
DROP POLICY IF EXISTS "cuentas_bancarias_update_own" ON cuentas_bancarias;
DROP POLICY IF EXISTS "cuentas_bancarias_delete_own" ON cuentas_bancarias;

ALTER TABLE cuentas_bancarias ADD COLUMN IF NOT EXISTS usuario_id_new VARCHAR(36);
UPDATE cuentas_bancarias SET usuario_id_new = CAST(usuario_id AS VARCHAR(36));
ALTER TABLE cuentas_bancarias DROP COLUMN usuario_id;
ALTER TABLE cuentas_bancarias ALTER COLUMN usuario_id_new RENAME TO usuario_id;

ALTER TABLE cuentas_bancarias ADD FOREIGN KEY (usuario_id) REFERENCES usuarios(id);

CREATE POLICY "cuentas_bancarias_read_own" ON cuentas_bancarias FOR SELECT USING (true);
CREATE POLICY "cuentas_bancarias_insert_own" ON cuentas_bancarias FOR INSERT WITH CHECK (true);
CREATE POLICY "cuentas_bancarias_update_own" ON cuentas_bancarias FOR UPDATE USING (true);
CREATE POLICY "cuentas_bancarias_delete_own" ON cuentas_bancarias FOR DELETE USING (true);

COMMIT;

-- =============================================
-- VERIFY
-- =============================================

SELECT
    table_name,
    column_name,
    data_type,
    character_maximum_length
FROM information_schema.columns
WHERE table_name IN ('usuarios', 'clientes', 'cuentas', 'cuentas_bancarias')
AND (column_name = 'id' OR column_name = 'usuario_id')
ORDER BY table_name, column_name;