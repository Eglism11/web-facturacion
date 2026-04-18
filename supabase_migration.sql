-- =============================================
-- Migration: Add usuario_id to clientes table
-- Run in Supabase SQL Editor
-- =============================================

-- Add usuario_id column to clientes table (INTEGER for local auth)
ALTER TABLE clientes 
ADD COLUMN IF NOT EXISTS usuario_id INTEGER REFERENCES usuarios(id);

-- Create index for better performance
CREATE INDEX IF NOT EXISTS idx_clientes_usuario_id ON clientes(usuario_id);

-- =============================================
-- Add usuario_id to cuentas table for direct ownership
-- =============================================

ALTER TABLE cuentas 
ADD COLUMN IF NOT EXISTS usuario_id INTEGER REFERENCES usuarios(id);

CREATE INDEX IF NOT EXISTS idx_cuentas_usuario_id ON cuentas(usuario_id);

-- =============================================
-- Enable RLS on all tables
-- =============================================

ALTER TABLE usuarios ENABLE ROW LEVEL SECURITY;
ALTER TABLE clientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE cuentas ENABLE ROW LEVEL SECURITY;
ALTER TABLE cuentas_bancarias ENABLE ROW LEVEL SECURITY;
ALTER TABLE firmas ENABLE ROW LEVEL SECURITY;

-- =============================================
-- POLICIES FOR USUARIOS
-- =============================================

DROP POLICY IF EXISTS "users_read_own" ON usuarios;
DROP POLICY IF EXISTS "users_update_own" ON usuarios;
DROP POLICY IF EXISTS "users_insert" ON usuarios;
DROP POLICY IF EXISTS "users_delete_own" ON usuarios;

CREATE POLICY "users_read_own" ON usuarios
    FOR SELECT USING (true);

CREATE POLICY "users_update_own" ON usuarios
    FOR UPDATE USING (true);

CREATE POLICY "users_insert" ON usuarios
    FOR INSERT WITH CHECK (true);

CREATE POLICY "users_delete_own" ON usuarios
    FOR DELETE USING (true);

-- =============================================
-- POLICIES FOR CLIENTES (filtered by usuario_id)
-- =============================================

DROP POLICY IF EXISTS "clientes_read_own" ON clientes;
DROP POLICY IF EXISTS "clientes_insert_own" ON clientes;
DROP POLICY IF EXISTS "clientes_update_own" ON clientes;
DROP POLICY IF EXISTS "clientes_delete_own" ON clientes;

CREATE POLICY "clientes_read_own" ON clientes
    FOR SELECT USING (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "clientes_insert_own" ON clientes
    FOR INSERT WITH CHECK (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "clientes_update_own" ON clientes
    FOR UPDATE USING (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "clientes_delete_own" ON clientes
    FOR DELETE USING (usuario_id::text = current_setting('app.current_user_id', true));

-- =============================================
-- POLICIES FOR CUENTAS (filtered by usuario_id)
-- =============================================

DROP POLICY IF EXISTS "cuentas_read_own" ON cuentas;
DROP POLICY IF EXISTS "cuentas_insert_own" ON cuentas;
DROP POLICY IF EXISTS "cuentas_update_own" ON cuentas;
DROP POLICY IF EXISTS "cuentas_delete_own" ON cuentas;

CREATE POLICY "cuentas_read_own" ON cuentas
    FOR SELECT USING (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "cuentas_insert_own" ON cuentas
    FOR INSERT WITH CHECK (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "cuentas_update_own" ON cuentas
    FOR UPDATE USING (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "cuentas_delete_own" ON cuentas
    FOR DELETE USING (usuario_id::text = current_setting('app.current_user_id', true));

-- =============================================
-- POLICIES FOR CUENTAS_BANCARIAS
-- =============================================

DROP POLICY IF EXISTS "cuentas_bancarias_read_own" ON cuentas_bancarias;
DROP POLICY IF EXISTS "cuentas_bancarias_insert_own" ON cuentas_bancarias;
DROP POLICY IF EXISTS "cuentas_bancarias_update_own" ON cuentas_bancarias;
DROP POLICY IF EXISTS "cuentas_bancarias_delete_own" ON cuentas_bancarias;

CREATE POLICY "cuentas_bancarias_read_own" ON cuentas_bancarias
    FOR SELECT USING (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "cuentas_bancarias_insert_own" ON cuentas_bancarias
    FOR INSERT WITH CHECK (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "cuentas_bancarias_update_own" ON cuentas_bancarias
    FOR UPDATE USING (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "cuentas_bancarias_delete_own" ON cuentas_bancarias
    FOR DELETE USING (usuario_id::text = current_setting('app.current_user_id', true));

-- =============================================
-- FIRMAS policies
-- =============================================

DROP POLICY IF EXISTS "firmas_read" ON firmas;
DROP POLICY IF EXISTS "firmas_insert" ON firmas;
DROP POLICY IF EXISTS "firmas_update" ON firmas;
DROP POLICY IF EXISTS "firmas_delete" ON firmas;

CREATE POLICY "firmas_read" ON firmas FOR SELECT USING (true);
CREATE POLICY "firmas_insert" ON firmas FOR INSERT WITH CHECK (true);
CREATE POLICY "firmas_update" ON firmas FOR UPDATE USING (true);
CREATE POLICY "firmas_delete" ON firmas FOR DELETE USING (true);

-- =============================================
-- Verify setup
-- =============================================

SELECT 
    'usuarios' as table_name,
    rowsecurity as rls_enabled
FROM pg_tables WHERE tablename = 'usuarios'
UNION ALL
SELECT 'clientes', rowsecurity FROM pg_tables WHERE tablename = 'clientes'
UNION ALL
SELECT 'cuentas', rowsecurity FROM pg_tables WHERE tablename = 'cuentas'
UNION ALL
SELECT 'cuentas_bancarias', rowsecurity FROM pg_tables WHERE tablename = 'cuentas_bancarias'
UNION ALL
SELECT 'firmas', rowsecurity FROM pg_tables WHERE tablename = 'firmas';