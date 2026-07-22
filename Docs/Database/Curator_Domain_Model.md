# Curator Domain Model

```mermaid
---
title: Curator Domain Model v0.2
---

erDiagram

    MODEL {
        UUID uuid
        string display_name
        string primary_name
        string description
        string country
        string ethnicity
        string eye_color
        string natural_hair_color
    }

    STUDIO {
        UUID uuid
        string name
        string website
        string description
    }

    STATUS {
        int id
        string name
    }

    ALBUM {
        UUID uuid
        string title
        string description
        string scene
        string location
        datetime capture_date
        datetime publish_date
        int rating
        string path
    }

    PHOTO {
        UUID uuid
        string filename
        string relative_path
        datetime capture_time
        string hash
        int width
        int height
    }

    ALBUM_MODEL {
        UUID uuid
        int age_when_shot
        string role
        string remarks
    }

    ALBUM_RELATION {
        int album_id
        int related_album_id
        string relation_type
        string remarks
    }

    WORKSPACE_ALBUM {
        int id
        string current_path
        string expected_path
        string primary_model
        string studio_name
        string album_name
        int belongs_to_album_id
        int album_id
    }

    ALBUM ||--|{ PHOTO : contains

    STUDIO ||--o{ ALBUM : publishes

    STATUS ||--o{ ALBUM : status

    MODEL ||--o{ ALBUM_MODEL : appears_in

    ALBUM ||--o{ ALBUM_MODEL : includes

    ALBUM ||--o{ ALBUM_RELATION : source

    ALBUM ||--o{ ALBUM_RELATION : related

    ALBUM ||--o{ WORKSPACE_ALBUM : materialized_as

    WORKSPACE_ALBUM ||--o{ WORKSPACE_ALBUM : belongs_to
```

## Domain Rules

- `album.path` is the permanent Album’s single canonical filesystem path. The permanent Album has no `current_path` or `expected_path` fields.
- `workspace_album` is temporary and may maintain both `current_path` and `expected_path` while processing is incomplete.
- `album_relation` represents an Album-to-Album relationship. For `BELONGS_TO`, `album_id` is a separately released part and `related_album_id` is its logical/canonical Album.
- A default/self relationship is implicit: do not store an `album_relation` row when both sides would be the same Album.
- `workspace_album.belongs_to_album_id` points to `workspace_album.id`. It must be translated to permanent Album IDs through `workspace_album.album_id` during migration.
