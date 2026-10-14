-- Read-only structural inventory. No student/account rows or credentials.
-- Run using an authorized read-only account and keep output in private-data/.
BEGIN TRANSACTION READ ONLY;

SELECT table_schema, table_name, ordinal_position, column_name, data_type,
       udt_name, character_maximum_length, numeric_precision, numeric_scale,
       is_nullable, column_default, is_identity
FROM information_schema.columns
WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
ORDER BY table_schema, table_name, ordinal_position;

SELECT n.nspname AS schema_name, t.relname AS table_name,
       c.conname AS constraint_name, c.contype AS constraint_type,
       pg_get_constraintdef(c.oid) AS definition
FROM pg_constraint c
JOIN pg_class t ON t.oid = c.conrelid
JOIN pg_namespace n ON n.oid = t.relnamespace
WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schema_name, table_name, constraint_name;

SELECT schemaname, tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
ORDER BY schemaname, tablename, indexname;

COMMIT;

-- Separately, if present and authorized, export only migration history:
-- SELECT app, name, applied FROM django_migrations ORDER BY app, name;
