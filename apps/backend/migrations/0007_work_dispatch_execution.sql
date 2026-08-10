-- BT-056: successful Work Dispatch preview claims are durable and single-use.
CREATE TABLE IF NOT EXISTS work_dispatch_preview_claim (
    preview_uuid TEXT PRIMARY KEY,
    batch_uuid TEXT NOT NULL UNIQUE,
    claimed_by_token_uuid TEXT NOT NULL,
    claimed_at TEXT NOT NULL,
    FOREIGN KEY(batch_uuid) REFERENCES work_dispatch_batch(uuid)
);

