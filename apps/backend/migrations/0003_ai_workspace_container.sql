-- BT-044: versioned AI Workspace container and first Album-analysis Dataset.
CREATE TABLE IF NOT EXISTS ai_dataset_schema (
    dataset_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('Active','Retired')),
    definition_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (dataset_type, schema_version)
);

CREATE TABLE IF NOT EXISTS ai_workspace (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    dataset_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    title TEXT NOT NULL,
    lifecycle_state TEXT NOT NULL DEFAULT 'Open'
        CHECK(lifecycle_state IN ('Open','Closed','Archived')),
    created_by_token_uuid TEXT,
    created_at TEXT NOT NULL,
    closed_at TEXT,
    archived_at TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    close_operation_uuid TEXT,
    archive_operation_uuid TEXT,
    FOREIGN KEY (dataset_type, schema_version)
        REFERENCES ai_dataset_schema(dataset_type, schema_version)
);

CREATE INDEX IF NOT EXISTS idx_ai_workspace_queue
    ON ai_workspace(lifecycle_state, created_at DESC);
