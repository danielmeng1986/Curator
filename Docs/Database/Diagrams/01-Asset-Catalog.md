# Asset Catalog ER Model

> Documentation status: Current
> Owner: Database
> Last verified: 2026-08-11

```mermaid
erDiagram
    STATUS {
        INTEGER id PK
        TEXT name
    }
    STUDIO {
        INTEGER id PK
        TEXT uuid UK
        TEXT name
    }
    MODEL {
        INTEGER id PK
        TEXT uuid UK
        TEXT primary_name
    }
    ALBUM {
        INTEGER id PK
        TEXT uuid UK
        INTEGER studio_id FK
        INTEGER status_id FK
        TEXT title
        TEXT path
        TEXT remark
    }
    PHOTO {
        INTEGER id PK
        TEXT uuid UK
        INTEGER album_id FK
        TEXT relative_path
        TEXT hash
    }
    ALBUM_MODEL {
        INTEGER id PK
        INTEGER album_id FK
        INTEGER model_id FK
        TEXT role
    }
    ALBUM_RELATION {
        INTEGER id PK
        INTEGER album_id FK
        INTEGER related_album_id FK
        TEXT relation_type
    }

    STATUS ||--o{ ALBUM : classifies
    STUDIO ||--o{ ALBUM : publishes
    ALBUM ||--o{ PHOTO : contains
    ALBUM ||--o{ ALBUM_MODEL : includes
    MODEL ||--o{ ALBUM_MODEL : appears_in
    ALBUM ||--o{ ALBUM_RELATION : source
    ALBUM ||--o{ ALBUM_RELATION : related_target
```

`album.path` is the canonical permanent path. `BELONGS_TO` relates a separately
released Album to its logical Album; self-relations are invalid. Exact FK and
uniqueness authority is recorded in the Schema Catalog because the deployed
base schema still awaits BT-059 canonical bootstrap consolidation.
