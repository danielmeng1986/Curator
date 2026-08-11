# DBDOC-005 — Archive Historical Workspace and v0.2 Guidance

## Task ID

`DBDOC-005` — Status: `Complete`

## Goal

Move completed v0.2 migration guidance and the retired `workspace_album` model
out of active database documentation while preserving their historical value.

## Scope

- Establish `Docs/Database/Historical/`.
- Move and rename the v0.2 Album path/relation migration instructions.
- Document `workspace_album` retirement, archive location, former relationship
  semantics, and prohibition on active client access.
- Replace active-document references with current AI Workspace and Work Dispatch concepts.

## Out of Scope

- Deleting migration history or archived source.
- Reactivating or redesigning the historical Workspace API.

## Inputs and Authority

- MT-008 and BT-043.
- Historical migration instructions and current Database diagrams/catalog.

## Deliverables

- `Docs/Database/Historical/Historical-Workspace-Album.md`.
- `Docs/Database/Historical/v0.2-Album-Path-and-Relation-Migration.md`.
- Updated links from active Database documents.

## Acceptance Criteria

- No active Database guide describes `workspace_album` as the current workspace.
- Historical IDs and `belongs_to_album_id` migration semantics remain documented.
- Historical documents have explicit completed/historical status and current replacements.
- Existing inbound links are updated or deliberately redirected.

## Verification

- Search active documentation for stale `workspace_album` guidance and classify
  every remaining occurrence as historical, exclusionary, or migration-specific.
- Verify all moved-document links.

## Dependencies

- DBDOC-003.
- DBDOC-004.

## Risks or Notes

- Historical facts must not be rewritten to resemble the new AI Workspace; they
  are different models with different lifecycle rules.

## Completion Record

- Relocated and relabeled the completed v0.2 migration instruction as Historical.
- Added the retired Workspace Album purpose, relationship translation,
  materialization checks, retirement evidence, and current replacement map.
- Removed the historical model from active diagram navigation while retaining
  explicit provenance links.
