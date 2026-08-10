# Operations, Repair, and Recovery ER Model

> Documentation status: Current
> Owner: Database
> Last verified: 2026-08-11

```mermaid
erDiagram
    ALBUM {
        INTEGER id PK
        TEXT uuid UK
        TEXT path
    }
    IMPORT_PREVIEW_CLAIM {
        TEXT preview_uuid PK
        TEXT claimed_at
    }
    OPERATION {
        INTEGER id PK
        TEXT uuid UK
        TEXT operation_type
        TEXT status
        TEXT entity_uuid
        TEXT related_operation_uuid
    }
    ISSUE {
        INTEGER id PK
        TEXT uuid UK
        TEXT affected_operation
        TEXT state
        TEXT source_workflow
    }
    ISSUE_LINK {
        TEXT issue_uuid
        TEXT relationship
        TEXT target_uuid
    }
    REPAIR_CASE {
        INTEGER id PK
        TEXT uuid UK
        TEXT operation_uuid
        TEXT album_uuid
        TEXT state
        TEXT verification_result
    }
    REPAIR_SUPPRESSION {
        INTEGER id PK
        TEXT uuid UK
        TEXT fingerprint
        TEXT scope_path
        TEXT expires_at
    }
    QUARANTINE_ITEM {
        TEXT uuid PK
        TEXT operation_uuid
        TEXT original_path
        TEXT quarantine_path
        TEXT expires_at
    }
    QUARANTINE_PREVIEW_CLAIM {
        TEXT preview_uuid PK
        TEXT claimed_at
    }
    SNAPSHOT_CLEANUP_PREVIEW_CLAIM {
        TEXT preview_uuid PK
        TEXT claimed_at
    }
    RESTORE_PREVIEW_CLAIM {
        TEXT preview_uuid PK
        TEXT claimed_at
    }

    ALBUM ||--o{ REPAIR_CASE : affected_logically
    OPERATION ||--o{ ISSUE : raises_logically
    ISSUE ||--o{ ISSUE_LINK : links
    OPERATION ||--o{ REPAIR_CASE : repair_chain
    OPERATION ||--o{ QUARANTINE_ITEM : records
```

Several edges are logical UUID links rather than physical SQLite FKs. Preview
claim tables are single-use execution bindings. Snapshot files themselves live
in Backend-controlled filesystem storage and therefore have no Snapshot entity
in this ER diagram.
