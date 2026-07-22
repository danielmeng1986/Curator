# Copilot Instructions: Curator Schema v0.2 and Data Migration

## Objective

Implement the v0.2 schema described in [Curator Database Model](Curator_Database_Model.md). Do not change unrelated tables or data. Work against `database/Curator.db` and make the migration safe, repeatable, and auditable.

The changes are:

1. Replace permanent Album path columns `current_path` and `expected_path` with one canonical `path` column.
2. Add the self-referencing `album_relation` table to preserve logical Album grouping, including relationships migrated from `workspace_album.belongs_to_album_id`.
3. Keep `workspace_album.current_path`, `workspace_album.expected_path`, and `workspace_album.belongs_to_album_id` unchanged: they are temporary-workspace fields.

## Required Target Schema

The permanent `album` table must have `path TEXT` and must not have `current_path` or `expected_path`.

Create this relationship table and indexes (SQLite syntax may be adapted to the project’s migration conventions):

```sql
CREATE TABLE album_relation (
    id INTEGER PRIMARY KEY,
    album_id INTEGER NOT NULL REFERENCES album(id),
    related_album_id INTEGER NOT NULL REFERENCES album(id),
    relation_type TEXT NOT NULL,
    remarks TEXT,
    CHECK (album_id <> related_album_id),
    UNIQUE (album_id, related_album_id, relation_type)
);

CREATE INDEX idx_album_relation_album_id ON album_relation(album_id);
CREATE INDEX idx_album_relation_related_album_id ON album_relation(related_album_id);
```

For this migration, write `relation_type = 'BELONGS_TO'`. `album_id` is the separately released Album and `related_album_id` is the logical/canonical Album it belongs to. Do not create a self-relation: default/self grouping is implicit.

## Preconditions and Backup

1. Inspect the live schema with `PRAGMA table_info` and `PRAGMA foreign_key_list`; do not assume the database exactly matches source documentation.
2. Create a timestamped SQLite backup before any write. Report its path.
3. Run the migration in one transaction where SQLite allows it, with foreign keys enabled. If rebuilding `album` requires temporarily disabling foreign-key enforcement, preserve every existing FK, index, and trigger, then run `PRAGMA foreign_key_check` before committing.
4. Make the migration idempotent. A rerun must not create duplicate `album_relation` rows or lose an existing `album.path` value.

## Path-Column Migration

SQLite cannot drop columns reliably across all supported versions. Rebuild the permanent `album` table if needed, preserving its primary keys, UUIDs, foreign keys, non-path columns, indexes, and data.

For every old Album row:

1. Read `current_path` and `expected_path`.
2. If both values are non-null and different, stop before writing, report the affected Album IDs and both values, and require a curator decision. Do not choose silently.
3. Otherwise set new `album.path` to the non-null value from `current_path` or `expected_path` (they are expected to be equal); retain null when both are null.
4. Remove `current_path` and `expected_path` only from the permanent `album` table. Do not alter the same-named workspace fields.

Update all code, queries, tests, import logic, and documentation that refer to permanent `album.current_path` or `album.expected_path` so they use `album.path`. Preserve `workspace_album.current_path` and `workspace_album.expected_path` references.

## Album-Relation Migration

Migrate after every relevant `workspace_album` has a valid `album_id` referencing its materialized permanent Album.

For each `workspace_album` source row:

1. Skip it if `belongs_to_album_id` is null or equals the source row’s `id`. These mean the default/self relationship.
2. Resolve the source permanent Album from `source_workspace.album_id`. Resolve the target workspace row by `source_workspace.belongs_to_album_id`, then resolve the target permanent Album from `target_workspace.album_id`.
3. If the target workspace row does not exist, or either `album_id` is null/invalid, do not create a partial relation. Report the source workspace ID, referenced workspace ID, and reason; fail the migration unless an explicit curator-approved exception policy is added.
4. If the resolved permanent Album IDs are equal, skip the relation as an implicit self/default relationship and log it.
5. Insert `album_relation(source_album_id, target_album_id, 'BELONGS_TO', NULL)` using conflict-safe insertion so reruns do not duplicate it.

Important: `workspace_album.belongs_to_album_id` does **not** reference `album.id`. It references `workspace_album.id`; conversion must go through the two `workspace_album.album_id` values.

## Verification and Deliverables

After migration, verify and report:

1. `album` contains `path` and no permanent `current_path`/`expected_path` columns.
2. Every permanent Album row retains the correct path value.
3. `workspace_album` retains both temporary path fields and `belongs_to_album_id`.
4. `album_relation` has no self-relations, no duplicate tuples, and every FK resolves.
5. The count of migrated `BELONGS_TO` links equals the count of valid non-self Workspace links, with skipped/invalid cases listed separately.
6. `PRAGMA foreign_key_check` returns no violations.
7. Automated tests cover: equal paths, one null path, conflicting paths, null/self workspace relation, valid cross-workspace relation, missing target workspace row, and rerunning the migration.

Deliver the migration script, tests, a concise migration report, and updates to the affected database/import/UI code. Do not run the migration against production data until the dry-run report has been reviewed.
