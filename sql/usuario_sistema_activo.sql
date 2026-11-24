-- SUPUESTO: el diagrama de la base no tiene columna para desactivar usuarios (RF-03).
-- Ejecutar una sola vez en el editor SQL de Supabase. No borra ni cambia datos existentes.
ALTER TABLE usuario_sistema ADD COLUMN IF NOT EXISTS activo BOOLEAN NOT NULL DEFAULT TRUE;
