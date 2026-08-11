# Historical Workspace Album

> Documentation status: Historical
> Owner: Database
> Last verified: 2026-08-11

## Status

`workspace_album` is the retired staging/review model used before the current AI
Workspace and Work Dispatch architecture. MT-008 verified that its rows were
already materialized into permanent Album records and archived them as retained
audit/migration evidence. BT-043 removed active client access.

It must not be used for new work, exposed by an active API/UI, or confused with
`workspace_album_ai_worker`, which is the current Album AI Work Item table.

## Former purpose

The table held temporary names, Studio/Model text, current and expected paths,
AI result text, former Status, a materialized permanent Album ID, and a
Workspace-to-Workspace `belongs_to_album_id` relationship while Albums were
prepared for the permanent catalog.

## Historical relationship semantics

- `workspace_album.album_id` resolved the materialized permanent Album.
- `workspace_album.belongs_to_album_id` referenced another
  `workspace_album.id`, never `album.id`.
- A null or self Workspace reference represented the implicit default relation.
- A non-self relationship was migrated by resolving both Workspace rows through
  their `album_id` values and writing permanent `album_relation` with
  `relation_type = 'BELONGS_TO'`.
- Invalid/missing targets were migration blockers; no partial relation was allowed.

## Retirement evidence

MT-008 required every row to have a valid materialized Album, matching canonical
path/name/Studio data, complete permanent Album relations, and no duplicate
Album paths before archive. Its guarded migration added lifecycle/archive
metadata, recorded a durable Operation, and retained all rows.

The archived classification is provenance, not an active lifecycle state
machine. Historical rows cannot be returned to Active/Review/Closed behavior.

## Current replacement

Current AI analysis uses separate, explicit concepts:

- `ai_workspace` for dataset-versioned containers;
- Work Dispatch Batch/Group/Reservation for Album assignment;
- `workspace_album_ai_worker` for adapter-owned Work Items;
- Manifest/result/review/rework tables for evidence and human decisions;
- Promotion for the single approved Album-name mutation;
- retention and closure records for durable history.

See the [Database Model](../Curator_Database_Model.md),
[Work Dispatch persistence](../Workflows/Work-Dispatch-Persistence.md), and
[AI review persistence](../Workflows/AI-Review-and-Promotion-Persistence.md).

## Historical sources

- MT-008 — Close and Archive Historical Workspace Albums
- BT-043 — Retire Historical Workspace Album Client API
- [v0.2 Album Path and Relation Migration](v0.2-Album-Path-and-Relation-Migration.md)
- `apps/backend/migrations/archive_workspace_album.py`
