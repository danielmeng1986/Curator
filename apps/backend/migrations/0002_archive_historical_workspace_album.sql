-- MT-008: historical workspace_album retention metadata.
-- The runner verifies every row is already materialized before applying this.
ALTER TABLE workspace_album ADD COLUMN lifecycle_state TEXT NOT NULL DEFAULT 'active';
ALTER TABLE workspace_album ADD COLUMN archive_classification TEXT;
ALTER TABLE workspace_album ADD COLUMN archive_reason TEXT;
ALTER TABLE workspace_album ADD COLUMN archived_at TEXT;
ALTER TABLE workspace_album ADD COLUMN archive_operation_uuid TEXT;
