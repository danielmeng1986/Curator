# AI Workspace ER Models

> Documentation status: Current
> Owner: Database
> Last verified: 2026-08-11

## Workspace, execution, and evidence

```mermaid
erDiagram
    ALBUM {
        INTEGER id PK
        TEXT uuid UK
        TEXT title
        TEXT path
    }
    AI_DATASET_SCHEMA {
        TEXT dataset_type PK
        INTEGER schema_version PK
        TEXT status
    }
    AI_WORKSPACE {
        INTEGER id PK
        TEXT uuid UK
        TEXT dataset_type FK
        INTEGER schema_version FK
        TEXT lifecycle_state
    }
    AI_WORKSPACE_RETENTION {
        TEXT workspace_uuid PK
        TEXT outcome_classification
        TEXT close_operation_uuid UK
    }
    AI_MODEL_CONFIGURATION {
        INTEGER id PK
        TEXT uuid UK
        TEXT name UK
        INTEGER sample_count
        INTEGER version
    }
    WORK_ITEM {
        INTEGER id PK
        TEXT uuid UK
        TEXT workspace_uuid FK
        INTEGER album_id FK
        TEXT ai_model_configuration_uuid FK
        TEXT run_state
    }
    WORK_ITEM_ATTEMPT {
        INTEGER id PK
        TEXT work_item_uuid FK
        INTEGER attempt_number
        TEXT outcome
    }
    EVIDENCE_MANIFEST {
        INTEGER id PK
        TEXT uuid UK
        TEXT work_item_uuid FK
        INTEGER album_id FK
        INTEGER sample_count
    }
    EVIDENCE_PHOTO {
        INTEGER id PK
        TEXT uuid UK
        TEXT manifest_uuid FK
        TEXT work_item_uuid FK
        INTEGER ordinal
        TEXT relative_path
        TEXT sha256
    }
    RESULT_STATE {
        TEXT work_item_uuid PK
        TEXT state
        TEXT vision_result_uuid
        TEXT writer_result_uuid
    }
    RESULT_STAGE {
        INTEGER id PK
        TEXT uuid UK
        TEXT work_item_uuid FK
        TEXT stage
        TEXT manifest_uuid FK
        TEXT payload_sha256
    }

    AI_DATASET_SCHEMA ||--o{ AI_WORKSPACE : versions
    AI_WORKSPACE ||--o| AI_WORKSPACE_RETENTION : retains
    AI_WORKSPACE ||--o{ WORK_ITEM : contains
    ALBUM ||--o{ WORK_ITEM : analyzed_by
    AI_MODEL_CONFIGURATION ||--o{ WORK_ITEM : configures
    WORK_ITEM ||--o{ WORK_ITEM_ATTEMPT : attempts
    WORK_ITEM ||--o| EVIDENCE_MANIFEST : samples
    EVIDENCE_MANIFEST ||--|{ EVIDENCE_PHOTO : contains
    WORK_ITEM ||--o| RESULT_STATE : projects
    WORK_ITEM ||--o{ RESULT_STAGE : records
    EVIDENCE_MANIFEST ||--o{ RESULT_STAGE : binds
```

## Review, rework, and Promotion

```mermaid
erDiagram
    ALBUM {
        INTEGER id PK
        TEXT uuid UK
        TEXT title
    }
    AI_WORKSPACE {
        INTEGER id PK
        TEXT uuid UK
    }
    WORK_ITEM {
        INTEGER id PK
        TEXT uuid UK
        TEXT workspace_uuid FK
        INTEGER album_id FK
    }
    REVIEW {
        TEXT work_item_uuid PK
        TEXT state
        INTEGER rating
        TEXT selected_name
        TEXT selection_source
    }
    REVIEW_DECISION {
        INTEGER id PK
        TEXT uuid UK
        TEXT work_item_uuid FK
        TEXT from_state
        TEXT to_state
        TEXT operation_uuid
    }
    REWORK {
        TEXT rework_of_work_item_uuid PK
        TEXT successor_work_item_uuid UK
        TEXT reason
    }
    PROMOTION {
        INTEGER id PK
        TEXT uuid UK
        TEXT preview_uuid UK
        TEXT workspace_uuid FK
        TEXT work_item_uuid FK
        INTEGER album_id FK
        TEXT outcome
    }
    PROMOTION_PREVIEW_CLAIM {
        TEXT preview_uuid PK
        TEXT promotion_uuid UK
        TEXT claimed_by_token_uuid
    }

    WORK_ITEM ||--o| REVIEW : current_review
    WORK_ITEM ||--o{ REVIEW_DECISION : decision_history
    WORK_ITEM ||--o| REWORK : predecessor
    WORK_ITEM ||--o| REWORK : successor
    AI_WORKSPACE ||--o{ PROMOTION : scopes
    WORK_ITEM ||--o| PROMOTION : wins
    ALBUM ||--o{ PROMOTION : renamed_by
    PROMOTION ||--o| PROMOTION_PREVIEW_CLAIM : claimed_from_preview
```

Review is a mutable projection; decisions are immutable history. Rework creates
a new Work Item and retains lineage. Partial unique indexes—not Mermaid
cardinality alone—enforce at most one successful Promotion per Workspace+Album
and per winning Work Item.
