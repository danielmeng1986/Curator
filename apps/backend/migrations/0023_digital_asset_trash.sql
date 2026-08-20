-- BT-034: retained Album/Photo lifecycle and recoverable Trash identity.
CREATE TABLE IF NOT EXISTS digital_asset_trash_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    album_id INTEGER NOT NULL UNIQUE REFERENCES album(id),
    original_relative_path TEXT NOT NULL,
    trash_relative_path TEXT NOT NULL UNIQUE,
    photo_count INTEGER NOT NULL,
    byte_count INTEGER NOT NULL,
    inventory_digest TEXT NOT NULL,
    retention_until TEXT NOT NULL,
    hold_reason TEXT,
    hold_by_token_uuid TEXT,
    hold_at TEXT,
    trash_operation_uuid TEXT NOT NULL,
    restore_operation_uuid TEXT,
    repair_uuid TEXT,
    issue_uuid TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_digital_asset_trash_retention
    ON digital_asset_trash_item(retention_until, hold_at);
