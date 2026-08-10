-- BT-054: generic Work Dispatch identity and Album-exclusive reservation.
CREATE TABLE IF NOT EXISTS work_dispatch_batch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    worker_kind TEXT NOT NULL,
    dataset_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    workspace_uuid TEXT,
    batch_state TEXT NOT NULL DEFAULT 'Active'
        CHECK(batch_state IN ('Active','Closed','Cancelled')),
    created_by_token_uuid TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS work_dispatch_group (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    batch_uuid TEXT NOT NULL,
    album_id INTEGER NOT NULL,
    worker_kind TEXT NOT NULL,
    dataset_type TEXT NOT NULL,
    schema_version INTEGER NOT NULL,
    group_state TEXT NOT NULL DEFAULT 'Active'
        CHECK(group_state IN ('Active','Released')),
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    released_at TEXT,
    released_by_token_uuid TEXT,
    release_reason TEXT,
    FOREIGN KEY(batch_uuid) REFERENCES work_dispatch_batch(uuid),
    FOREIGN KEY(album_id) REFERENCES album(id)
);
CREATE INDEX IF NOT EXISTS idx_work_dispatch_group_album_history
    ON work_dispatch_group(album_id, created_at DESC, id DESC);

-- Only active ownership lives here. Deleting this row releases the Album while
-- work_dispatch_group preserves the complete historical assignment.
CREATE TABLE IF NOT EXISTS album_work_reservation (
    album_id INTEGER PRIMARY KEY,
    group_uuid TEXT NOT NULL UNIQUE,
    batch_uuid TEXT NOT NULL,
    worker_kind TEXT NOT NULL,
    reserved_at TEXT NOT NULL,
    FOREIGN KEY(album_id) REFERENCES album(id),
    FOREIGN KEY(group_uuid) REFERENCES work_dispatch_group(uuid),
    FOREIGN KEY(batch_uuid) REFERENCES work_dispatch_batch(uuid)
);

-- Polymorphic association: the dispatch layer knows Item identity and kind,
-- while each Worker adapter owns the Item's schema and lifecycle.
CREATE TABLE IF NOT EXISTS work_dispatch_group_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_uuid TEXT NOT NULL,
    item_kind TEXT NOT NULL,
    item_uuid TEXT NOT NULL,
    configuration_uuid TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(group_uuid, item_kind, item_uuid),
    UNIQUE(item_kind, item_uuid),
    FOREIGN KEY(group_uuid) REFERENCES work_dispatch_group(uuid)
);
CREATE INDEX IF NOT EXISTS idx_work_dispatch_group_item_group
    ON work_dispatch_group_item(group_uuid, created_at, id);

