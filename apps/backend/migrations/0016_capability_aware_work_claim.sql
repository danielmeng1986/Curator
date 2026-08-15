-- BT-063: immutable required Worker kind and claim capability audit snapshot.
ALTER TABLE workspace_album_ai_worker
    ADD COLUMN worker_kind TEXT NOT NULL DEFAULT 'album_name_analysis';
ALTER TABLE ai_work_item_attempt
    ADD COLUMN worker_kinds_json TEXT;
CREATE INDEX IF NOT EXISTS idx_ai_work_item_kind_queue
    ON workspace_album_ai_worker(worker_kind, run_state, created_at, id);
