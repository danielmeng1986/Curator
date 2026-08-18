-- Preconditions: 0005 Work Items and 0007 Dispatch Groups are present.
-- Preservation: additive lineage only; existing Work Items, Manifests, and
-- result stages are unchanged. Verification is covered by migration and
-- successor workflow tests. Recovery uses the runner's verified pre-migration
-- backup; the table may otherwise remain empty until an Admin requests rerun.
CREATE TABLE IF NOT EXISTS ai_work_item_regeneration (
    predecessor_work_item_uuid TEXT NOT NULL UNIQUE,
    successor_work_item_uuid TEXT NOT NULL UNIQUE,
    root_work_item_uuid TEXT NOT NULL,
    generation_number INTEGER NOT NULL CHECK(generation_number BETWEEN 1 AND 3),
    selection_seed INTEGER NOT NULL,
    reason TEXT NOT NULL,
    requested_by_token_uuid TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(predecessor_work_item_uuid) REFERENCES workspace_album_ai_worker(uuid),
    FOREIGN KEY(successor_work_item_uuid) REFERENCES workspace_album_ai_worker(uuid),
    FOREIGN KEY(root_work_item_uuid) REFERENCES workspace_album_ai_worker(uuid)
);

CREATE INDEX IF NOT EXISTS idx_ai_work_item_regeneration_root
    ON ai_work_item_regeneration(root_work_item_uuid, generation_number);
