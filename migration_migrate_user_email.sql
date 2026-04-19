-- Migration: Update existing user with email
-- Run in Supabase SQL Editor
-- =============================================

UPDATE usuarios
SET email = 'eglismontes11@gmail.com'
WHERE email = 'eglis';

-- Verify
SELECT id, email, nombre_completo FROM usuarios WHERE email = 'eglismontes11@gmail.com';