-- =============================================
-- Security Fix Migration
-- Run in Supabase SQL Editor
-- =============================================

BEGIN;

-- =============================================
-- 1. Fix FIRMAS: usuario_id column (if not exists)
-- =============================================

ALTER TABLE firmas ADD COLUMN IF NOT EXISTS usuario_id VARCHAR(36);
ALTER TABLE firmas ADD CONSTRAINT fk_firmas_usuario FOREIGN KEY (usuario_id) REFERENCES usuarios(id);

CREATE INDEX IF NOT EXISTS idx_firmas_usuario_id ON firmas(usuario_id);

-- =============================================
-- 2. Fix RLS policies for FIRMAS (by usuario_id)
-- =============================================

DROP POLICY IF EXISTS "firmas_read" ON firmas;
DROP POLICY IF EXISTS "firmas_insert" ON firmas;
DROP POLICY IF EXISTS "firmas_update" ON firmas;
DROP POLICY IF EXISTS "firmas_delete" ON firmas;

CREATE POLICY "firmas_read_own" ON firmas
    FOR SELECT USING (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "firmas_insert_own" ON firmas
    FOR INSERT WITH CHECK (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "firmas_update_own" ON firmas
    FOR UPDATE USING (usuario_id::text = current_setting('app.current_user_id', true));

CREATE POLICY "firmas_delete_own" ON firmas
    FOR DELETE USING (usuario_id::text = current_setting('app.current_user_id', true));

-- =============================================
-- 3. Add constraints: NOT NULL on required fields
-- =============================================

ALTER TABLE clientes ALTER COLUMN nombre SET NOT NULL;
ALTER TABLE cuentas ALTER COLUMN concepto SET NOT NULL;
ALTER TABLE cuentas ALTER COLUMN monto SET NOT NULL;

-- =============================================
-- 4. Add unique constraints (prevent duplicates)
-- =============================================

ALTER TABLE usuarios ADD CONSTRAINT uq_usuario_username UNIQUE (username);
ALTER TABLE cuentas ADD CONSTRAINT uq_cuenta_numero_factura UNIQUE (numero_factura);

-- =============================================
-- 5. Add check constraints
-- =============================================

ALTER TABLE cuentas ADD CONSTRAINT chk_monto_positivo CHECK (monto > 0);
ALTER TABLE cuentas ADD CONSTRAINT chk_estado_valido CHECK (estado IN ('pendiente', 'pagado', 'cancelado'));

COMMIT;

-- =============================================
-- Verify
-- =============================================

SELECT
    tc.table_name,
    tc.constraint_name,
    tc.constraint_type
FROM information_schema.table_constraints tc
WHERE tc.table_name IN ('usuarios', 'clientes', 'cuentas', 'firmas', 'cuentas_bancarias')
AND tc.constraint_type IS NOT NULL
ORDER BY tc.table_name, tc.constraint_name;