-- BT-059: canonical pre-migration Curator catalog bootstrap.
CREATE TABLE IF NOT EXISTS status (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT
);
CREATE TABLE IF NOT EXISTS model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    display_name TEXT,
    primary_name TEXT,
    description TEXT,
    country TEXT,
    ethnicity TEXT,
    eye_color TEXT,
    natural_hair_color TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS studio (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    name TEXT,
    website TEXT,
    description TEXT,
    media_scope TEXT,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS album (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    studio_id INTEGER REFERENCES studio(id),
    status_id INTEGER REFERENCES status(id),
    title TEXT,
    description TEXT,
    scene TEXT,
    location TEXT,
    capture_date TEXT,
    publish_date TEXT,
    rating REAL,
    path TEXT,
    catalog_state TEXT NOT NULL DEFAULT 'ACTIVE'
        CHECK(catalog_state IN ('ACTIVE','TRASHED')),
    asset_state TEXT NOT NULL DEFAULT 'PRESENT'
        CHECK(asset_state IN ('PRESENT','TRASHED','DELETED','MISSING','NEEDS_REPAIR')),
    lifecycle_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT,
    updated_at TEXT
);
CREATE TABLE IF NOT EXISTS album_model (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id INTEGER NOT NULL REFERENCES album(id),
    model_id INTEGER NOT NULL REFERENCES model(id),
    age_when_shot REAL,
    role TEXT,
    remarks TEXT,
    UNIQUE(album_id, model_id)
);
CREATE TABLE IF NOT EXISTS album_relation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    album_id INTEGER NOT NULL REFERENCES album(id),
    related_album_id INTEGER NOT NULL REFERENCES album(id),
    relation_type TEXT NOT NULL,
    remarks TEXT,
    CHECK(album_id <> related_album_id),
    UNIQUE(album_id, related_album_id, relation_type)
);
CREATE INDEX IF NOT EXISTS idx_album_relation_album_id ON album_relation(album_id);
CREATE INDEX IF NOT EXISTS idx_album_relation_related_album_id ON album_relation(related_album_id);
CREATE TABLE IF NOT EXISTS photo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    album_id INTEGER NOT NULL REFERENCES album(id),
    filename TEXT,
    relative_path TEXT,
    hash TEXT,
    width INTEGER,
    height INTEGER,
    capture_time TEXT,
    asset_state TEXT NOT NULL DEFAULT 'PRESENT'
        CHECK(asset_state IN ('PRESENT','TRASHED','DELETED','MISSING','NEEDS_REPAIR')),
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS workspace_album (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT,
    status_id INTEGER REFERENCES status(id),
    studio_name TEXT,
    album_name TEXT,
    primary_model TEXT,
    additional_models TEXT,
    remark TEXT,
    current_path TEXT,
    expected_path TEXT,
    ai_result TEXT,
    belongs_to_album_id INTEGER REFERENCES workspace_album(id),
    album_id INTEGER REFERENCES album(id)
);
