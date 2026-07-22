# Safety and Acceptance

## Validation, Safety, and Audit

The UI follows Curator’s reviewable, traceable, and reversible workflow principles.

- Validate required values, dates, numeric values, duplicate relationships, foreign-key existence, and path conflicts before enabling Save or Import.
- Use inline field validation plus a page-level summary for blocked operations.
- Preview every multi-record change and import; do not apply bulk operations directly from a selected grid.
- Record each create, update, delete, batch operation, and import with timestamp, affected records, before/after values where applicable, and outcome. Provide an operation-history link from success feedback.
- Create a database snapshot before imports and material batch operations. Identify the snapshot/operation reference in the result view.
- Confirm deletion, batch updates, and filesystem-changing imports with a dialog that names scope and irreversible effects.
- Retain unsaved input when database locking, validation, or filesystem access fails.

## Out of Scope

- Public access, authentication, roles, or cloud synchronization.
- A generic raw SQL table editor.
- Editing generated IDs, UUIDs, or audit timestamps.
- A top-level CRUD page for `album_model` or `album_relation`; both relationships are instead maintained in the Album form.
- Automated acceptance of AI suggestions.
- Silent conversion of Workspace Albums into permanent Albums; any future conversion requires a separately reviewed field-mapping flow.

## Acceptance Criteria

The plan is fulfilled when a local user can:

1. browse, search, create, and edit Models, Studios, Statuses, Albums, Photos, and Workspace Albums under the data interaction rules;
2. create Models and Studios either from their lists or without leaving Album/Import workflows;
3. use readable names for all foreign-key interactions and navigate to referenced entities;
4. add, remove, and edit Models / Additional Models from Album details, with those actions correctly creating, deleting, or updating `album_model` records rather than writing Model data to `album`;
5. add and remove logical/release Album links from Album details, with those actions correctly creating or deleting non-self `album_relation` records;
6. review and batch-edit Workspace Albums without editing system-managed fields, while keeping workspace-to-workspace `belongs_to_album_id` distinct from permanent Album IDs;
7. select folders, review parsed data/conflicts, and batch-import valid selections directly to `album` with related Studio, Model, `album_model`, and optional `album_relation` records;
8. receive preview, explicit confirmation, and auditable outcomes for all material batches and imports.
