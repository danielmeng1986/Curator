-- MT-007: add the permanent, nullable curator business remark to album.
--
-- Preconditions: album exists.  The migration runner checks the live schema,
-- creates and verifies a SQLite backup before writing, and records this source
-- version in schema_migration.  It skips this statement when the column is
-- already present, so an older manually-updated database can be adopted safely.
--
-- Recovery: stop the Backend and restore the backup reported by the runner.
ALTER TABLE album ADD COLUMN remark TEXT;
