-- BT-052: indefinite audit retention and explicit Workspace lifecycle evidence.
CREATE TABLE IF NOT EXISTS ai_workspace_retention (
    workspace_uuid TEXT PRIMARY KEY,
    retention_classification TEXT NOT NULL DEFAULT 'IndefiniteAudit'
        CHECK(retention_classification='IndefiniteAudit'),
    outcome_classification TEXT NOT NULL
        CHECK(outcome_classification IN ('Completed','Rejected','Cancelled','Abandoned','Mixed')),
    close_reason TEXT NOT NULL,
    closed_by_token_uuid TEXT NOT NULL,
    closed_at TEXT NOT NULL,
    close_operation_uuid TEXT NOT NULL UNIQUE,
    archive_reason TEXT,
    archived_by_token_uuid TEXT,
    archived_at TEXT,
    archive_operation_uuid TEXT UNIQUE,
    FOREIGN KEY(workspace_uuid) REFERENCES ai_workspace(uuid)
);
