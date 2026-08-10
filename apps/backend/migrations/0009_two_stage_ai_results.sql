-- BT-049: immutable, ordered Vision and Writer result stages.
CREATE TABLE IF NOT EXISTS ai_work_item_result_state (
    work_item_uuid TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'AwaitingVision'
        CHECK(state IN ('AwaitingVision','AwaitingWriter','ReadyForReview')),
    vision_result_uuid TEXT,
    writer_result_uuid TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(work_item_uuid) REFERENCES workspace_album_ai_worker(uuid)
);
CREATE TABLE IF NOT EXISTS ai_work_item_result_stage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    work_item_uuid TEXT NOT NULL,
    stage TEXT NOT NULL CHECK(stage IN ('Vision','Writer')),
    schema_version TEXT NOT NULL,
    manifest_uuid TEXT NOT NULL,
    manifest_version INTEGER NOT NULL,
    configuration_snapshot_sha256 TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    payload_sha256 TEXT NOT NULL,
    runtime_metrics_json TEXT NOT NULL,
    operation_uuid TEXT NOT NULL,
    submitted_by_token_uuid TEXT NOT NULL,
    submitted_at TEXT NOT NULL,
    UNIQUE(work_item_uuid, stage),
    FOREIGN KEY(work_item_uuid) REFERENCES workspace_album_ai_worker(uuid),
    FOREIGN KEY(manifest_uuid) REFERENCES ai_photo_evidence_manifest(uuid)
);
