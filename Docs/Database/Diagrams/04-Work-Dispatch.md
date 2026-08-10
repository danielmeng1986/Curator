# Work Dispatch ER Model

> Documentation status: Current
> Owner: Database
> Last verified: 2026-08-11

```mermaid
erDiagram
    ALBUM {
        INTEGER id PK
        TEXT uuid UK
        TEXT title
    }
    WORK_DISPATCH_BATCH {
        INTEGER id PK
        TEXT uuid UK
        TEXT worker_kind
        TEXT batch_state
        TEXT workspace_uuid
    }
    WORK_DISPATCH_GROUP {
        INTEGER id PK
        TEXT uuid UK
        TEXT batch_uuid FK
        INTEGER album_id FK
        TEXT group_state
    }
    ALBUM_WORK_RESERVATION {
        INTEGER album_id PK
        TEXT group_uuid FK
        TEXT batch_uuid FK
        TEXT worker_kind
    }
    WORK_DISPATCH_GROUP_ITEM {
        INTEGER id PK
        TEXT group_uuid FK
        TEXT item_kind
        TEXT item_uuid
        TEXT configuration_uuid
    }
    WORK_DISPATCH_PREVIEW_CLAIM {
        TEXT preview_uuid PK
        TEXT batch_uuid UK
        TEXT claimed_by_token_uuid
    }
    WORK_DISPATCH_GROUP_CLOSURE {
        TEXT group_uuid PK
        TEXT disposition
        TEXT operation_uuid UK
        TEXT closed_at
    }

    ALBUM ||--o{ WORK_DISPATCH_GROUP : assignment_history
    WORK_DISPATCH_BATCH ||--|{ WORK_DISPATCH_GROUP : contains
    ALBUM ||--o| ALBUM_WORK_RESERVATION : actively_reserves
    WORK_DISPATCH_GROUP ||--o| ALBUM_WORK_RESERVATION : owns
    WORK_DISPATCH_BATCH ||--o{ ALBUM_WORK_RESERVATION : groups
    WORK_DISPATCH_GROUP ||--|{ WORK_DISPATCH_GROUP_ITEM : adapts
    WORK_DISPATCH_BATCH ||--o| WORK_DISPATCH_PREVIEW_CLAIM : claimed_by_preview
    WORK_DISPATCH_GROUP ||--o| WORK_DISPATCH_GROUP_CLOSURE : closes
```

The Reservation row is the active cross-Worker lock and is deleted on release.
Batch, Group, Item links, and Closure remain as history. `item_kind + item_uuid`
is a polymorphic adapter identity; for Album AI work it points to
`workspace_album_ai_worker`, without a physical cross-adapter FK.
