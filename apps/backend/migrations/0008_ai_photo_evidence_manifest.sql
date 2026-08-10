-- BT-047: immutable Backend-selected Album Photo evidence.
CREATE TABLE IF NOT EXISTS ai_photo_evidence_manifest (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    work_item_uuid TEXT NOT NULL UNIQUE,
    album_id INTEGER NOT NULL,
    manifest_version INTEGER NOT NULL DEFAULT 1,
    sample_count INTEGER NOT NULL,
    eligible_image_count INTEGER NOT NULL,
    average_size_bytes REAL NOT NULL,
    selection_method TEXT NOT NULL,
    discovery_summary_json TEXT NOT NULL,
    selected_at TEXT NOT NULL,
    FOREIGN KEY(work_item_uuid) REFERENCES workspace_album_ai_worker(uuid),
    FOREIGN KEY(album_id) REFERENCES album(id)
);
CREATE TABLE IF NOT EXISTS workspace_album_ai_worker_photo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    manifest_uuid TEXT NOT NULL,
    work_item_uuid TEXT NOT NULL,
    album_id INTEGER NOT NULL,
    ordinal INTEGER NOT NULL,
    relative_path TEXT NOT NULL,
    filename TEXT NOT NULL,
    size_bytes INTEGER NOT NULL,
    modified_time_ns INTEGER NOT NULL,
    sha256 TEXT NOT NULL,
    mime_type TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(manifest_uuid, ordinal),
    UNIQUE(manifest_uuid, relative_path),
    FOREIGN KEY(manifest_uuid) REFERENCES ai_photo_evidence_manifest(uuid),
    FOREIGN KEY(work_item_uuid) REFERENCES workspace_album_ai_worker(uuid),
    FOREIGN KEY(album_id) REFERENCES album(id)
);

