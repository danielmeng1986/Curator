-- BT-059: canonical Authentication and operational workflow persistence.
CREATE TABLE IF NOT EXISTS device_registration (
    uuid TEXT PRIMARY KEY, device_name TEXT NOT NULL,
    device_identity TEXT NOT NULL UNIQUE, requested_role TEXT NOT NULL,
    requested_scopes TEXT NOT NULL, approved_role TEXT, approved_scopes TEXT,
    status TEXT NOT NULL, trusted INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    approved_at TEXT, rejected_at TEXT
);
CREATE TABLE IF NOT EXISTS auth_token (
    uuid TEXT PRIMARY KEY, token_hash TEXT NOT NULL UNIQUE,
    registration_uuid TEXT NOT NULL, device_name TEXT NOT NULL,
    scopes TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
    last_used_at TEXT, revoked_at TEXT, replaced_by_uuid TEXT,
    FOREIGN KEY(registration_uuid) REFERENCES device_registration(uuid)
);
CREATE TABLE IF NOT EXISTS token_renewal_request (
    uuid TEXT PRIMARY KEY, registration_uuid TEXT NOT NULL,
    previous_token_uuid TEXT NOT NULL, requested_role TEXT NOT NULL,
    requested_scopes TEXT NOT NULL, status TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
    approved_at TEXT, rejected_at TEXT,
    FOREIGN KEY(registration_uuid) REFERENCES device_registration(uuid),
    FOREIGN KEY(previous_token_uuid) REFERENCES auth_token(uuid)
);
CREATE TABLE IF NOT EXISTS admin_bootstrap_code (
    uuid TEXT PRIMARY KEY, code_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL, expires_at TEXT NOT NULL, used_at TEXT,
    failed_attempts INTEGER NOT NULL DEFAULT 0, locked_at TEXT
);
CREATE TABLE IF NOT EXISTS import_preview_claim (
    preview_uuid TEXT PRIMARY KEY, claimed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS repair_case (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL UNIQUE,
    operation_uuid TEXT, album_uuid TEXT, expected_path TEXT,
    state TEXT NOT NULL DEFAULT 'NeedsRepair',
    category TEXT NOT NULL DEFAULT 'Assisted', confirmation TEXT,
    failure_reason TEXT, verification_result TEXT,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS repair_suppression (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL UNIQUE,
    fingerprint TEXT NOT NULL, scope_path TEXT NOT NULL, reason TEXT NOT NULL,
    creator TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
    revoked_at TEXT, revoked_by TEXT
);
CREATE TABLE IF NOT EXISTS snapshot_cleanup_preview_claim (
    preview_uuid TEXT PRIMARY KEY, claimed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS restore_preview_claim (
    preview_uuid TEXT PRIMARY KEY, claimed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quarantine_item (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL UNIQUE,
    original_path TEXT NOT NULL, quarantine_path TEXT NOT NULL,
    repair_uuid TEXT, operation_uuid TEXT NOT NULL, reason TEXT NOT NULL,
    inventory TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
    hold INTEGER NOT NULL DEFAULT 0, restored_at TEXT,
    restore_operation_uuid TEXT, restore_destination TEXT
);
CREATE TABLE IF NOT EXISTS quarantine_preview_claim (
    preview_uuid TEXT PRIMARY KEY, claimed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS issue (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL, description TEXT NOT NULL,
    affected_operation TEXT, suggested_resolution TEXT,
    state TEXT NOT NULL DEFAULT 'Open', source_workflow TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT, priority TEXT DEFAULT 'Normal',
    owner TEXT, due_date TEXT, resolution_verification TEXT,
    resolved_by TEXT, resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS issue_link (
    issue_uuid TEXT NOT NULL, relationship TEXT NOT NULL,
    target_uuid TEXT NOT NULL, created_at TEXT NOT NULL,
    UNIQUE(issue_uuid, relationship, target_uuid)
);
CREATE TABLE IF NOT EXISTS operation (
    id INTEGER PRIMARY KEY AUTOINCREMENT, uuid TEXT NOT NULL,
    operation_type TEXT NOT NULL, initiator TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'Pending', summary TEXT,
    started_at TEXT NOT NULL, ended_at TEXT, entity_uuid TEXT,
    import_uuid TEXT, batch_uuid TEXT, repair_uuid TEXT,
    related_operation_uuid TEXT, parent_operation_uuid TEXT, issue_uuid TEXT,
    error_category TEXT, error_code TEXT, error_details TEXT,
    repair_state TEXT, recovery_context TEXT
);

