-- BT-046: Album AI Work Items and durable Worker attempts.
CREATE TABLE IF NOT EXISTS workspace_album_ai_worker (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL UNIQUE,
    workspace_uuid TEXT NOT NULL, album_id INTEGER NOT NULL,
    ai_model_configuration_uuid TEXT NOT NULL,
    configuration_snapshot_json TEXT NOT NULL,
    run_state TEXT NOT NULL DEFAULT 'Pending'
        CHECK(run_state IN ('Pending','Claimed','Failed','Cancelled','Completed')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    claimed_by_token_uuid TEXT, lease_expires_at TEXT, last_error TEXT,
    version INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    FOREIGN KEY(workspace_uuid) REFERENCES ai_workspace(uuid),
    FOREIGN KEY(album_id) REFERENCES album(id),
    FOREIGN KEY(ai_model_configuration_uuid) REFERENCES ai_model_configuration(uuid)
);
CREATE INDEX IF NOT EXISTS idx_ai_work_item_queue
    ON workspace_album_ai_worker(run_state, created_at, id);
CREATE TABLE IF NOT EXISTS ai_work_item_attempt (
    id INTEGER PRIMARY KEY AUTOINCREMENT, work_item_uuid TEXT NOT NULL,
    attempt_number INTEGER NOT NULL, worker_token_uuid TEXT NOT NULL,
    claimed_at TEXT NOT NULL, lease_expires_at TEXT NOT NULL,
    ended_at TEXT, outcome TEXT, error_code TEXT, error_message TEXT,
    UNIQUE(work_item_uuid, attempt_number),
    FOREIGN KEY(work_item_uuid) REFERENCES workspace_album_ai_worker(uuid)
);
