-- BT-050: stable human review, immutable decisions, and rework lineage.
CREATE TABLE IF NOT EXISTS ai_work_item_review (
    work_item_uuid TEXT PRIMARY KEY,
    state TEXT NOT NULL DEFAULT 'ReadyForReview'
        CHECK(state IN ('ReadyForReview','InReview','Approved','Rejected','ReworkRequested')),
    rating INTEGER CHECK(rating BETWEEN 1 AND 5),
    notes TEXT,
    selected_name TEXT,
    selection_source TEXT CHECK(selection_source IN ('Recommendation','HumanRevision')),
    selected_recommendation TEXT,
    reviewer_token_uuid TEXT,
    review_started_at TEXT,
    decided_at TEXT,
    decision_reason TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    latest_operation_uuid TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(work_item_uuid) REFERENCES workspace_album_ai_worker(uuid)
);
CREATE TABLE IF NOT EXISTS ai_work_item_review_decision (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    work_item_uuid TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    reviewer_token_uuid TEXT NOT NULL,
    operation_uuid TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(work_item_uuid) REFERENCES workspace_album_ai_worker(uuid)
);
CREATE TABLE IF NOT EXISTS ai_work_item_rework (
    rework_of_work_item_uuid TEXT NOT NULL UNIQUE,
    successor_work_item_uuid TEXT NOT NULL UNIQUE,
    reason TEXT NOT NULL,
    requested_by_token_uuid TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(rework_of_work_item_uuid) REFERENCES workspace_album_ai_worker(uuid),
    FOREIGN KEY(successor_work_item_uuid) REFERENCES workspace_album_ai_worker(uuid)
);
CREATE INDEX IF NOT EXISTS idx_ai_work_item_review_queue ON ai_work_item_review(state, updated_at DESC);
