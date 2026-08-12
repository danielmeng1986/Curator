-- UI-only Reader/Writer enrollment with hash-only managed credentials.
CREATE TABLE IF NOT EXISTS registration_proof_state (
    singleton INTEGER PRIMARY KEY CHECK (singleton = 1),
    proof_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    rotated_at TEXT,
    disabled_at TEXT,
    last_used_at TEXT
);
ALTER TABLE device_registration ADD COLUMN candidate_token_hash TEXT;
ALTER TABLE device_registration ADD COLUMN enrollment_proof_hash TEXT;
ALTER TABLE device_registration ADD COLUMN enrollment_expires_at TEXT;
ALTER TABLE device_registration ADD COLUMN cancelled_at TEXT;
