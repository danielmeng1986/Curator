-- BT-057: explicit Group closure outcome and retained release evidence.
CREATE TABLE IF NOT EXISTS work_dispatch_group_closure (
    group_uuid TEXT PRIMARY KEY,
    disposition TEXT NOT NULL CHECK(disposition IN ('Closed','Cancelled','Abandoned')),
    reason TEXT NOT NULL,
    closed_by_token_uuid TEXT NOT NULL,
    operation_uuid TEXT NOT NULL UNIQUE,
    summary_json TEXT NOT NULL,
    closed_at TEXT NOT NULL,
    FOREIGN KEY(group_uuid) REFERENCES work_dispatch_group(uuid)
);
