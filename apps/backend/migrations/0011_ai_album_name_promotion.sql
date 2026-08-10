-- BT-051: one successful Album-name winner per Workspace and Album.
CREATE TABLE IF NOT EXISTS workspace_album_name_promotion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT NOT NULL UNIQUE,
    preview_uuid TEXT NOT NULL UNIQUE,
    workspace_uuid TEXT NOT NULL,
    work_item_uuid TEXT NOT NULL,
    album_id INTEGER NOT NULL,
    selected_name TEXT NOT NULL,
    prior_title TEXT,
    prior_status_id INTEGER,
    resulting_status_id INTEGER,
    outcome TEXT NOT NULL CHECK(outcome IN ('Promoted','PromotionFailed')),
    promoted_by_token_uuid TEXT NOT NULL,
    operation_uuid TEXT NOT NULL,
    snapshot_reference TEXT,
    promoted_at TEXT NOT NULL,
    FOREIGN KEY(workspace_uuid) REFERENCES ai_workspace(uuid),
    FOREIGN KEY(work_item_uuid) REFERENCES workspace_album_ai_worker(uuid),
    FOREIGN KEY(album_id) REFERENCES album(id)
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_promotion_workspace_album_winner
    ON workspace_album_name_promotion(workspace_uuid,album_id) WHERE outcome='Promoted';
CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_promotion_work_item_winner
    ON workspace_album_name_promotion(work_item_uuid) WHERE outcome='Promoted';
CREATE TABLE IF NOT EXISTS ai_promotion_preview_claim (
    preview_uuid TEXT PRIMARY KEY,
    promotion_uuid TEXT NOT NULL UNIQUE,
    claimed_by_token_uuid TEXT NOT NULL,
    claimed_at TEXT NOT NULL
);
