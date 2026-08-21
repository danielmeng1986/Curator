# UI-005 — Adapt Permanent Entity Management UI

## Task ID

`UI-005` — Status: `Complete`

## Title

Adapt Permanent Entity Management to the Supported API

## Related Specification(s)

- [UI Data Interaction Rules](../Data-Interaction-Rules.md).
- [UI Entity Management](../Features/Entity-Management.md).
- [API Specification](../../Backend/Specifications/API-Specification.md).

## Goal

Complete and normalize Album, Model, Studio, Status, and relationship
management against authenticated `/api/v1` contracts, with Album as the
minimum routine digital-asset management unit.

## Scope

- Lists, search, filters, sorting, pagination, create, edit, and protected Album Trash hand-off.
- Album–Model and Album–Album relationships inside Album detail.
- Inline Model/Studio creation where specified, role-aware actions, validation, and retained drafts.

## Out of Scope

- Import, Workspace, Issue/Repair, raw relationship-table screens, and routine Photo browsing/CRUD.
- Direct Album hard deletion or filesystem removal before the Digital Asset Trash lifecycle is ready.
- Backend business-rule changes not required by the approved UI contract.

## Dependencies

- UI-001 and UI-002.
- `BT-032` for Album query, batch mutation, and relationship validation contracts.
- `BT-033`, `BT-034`, and `UI-037` before enabling Album Trash. Permanent
  purge remains gated separately by `BT-035` and `UI-010E`.
- Supported canonical read/write models for each exposed entity surface.

## Implementation Steps

1. Audit current pages against UI field/editability and API contracts.
2. Remove routine Photo management, close behavior and usability gaps by entity, and preserve relationship boundaries.
3. Add client contract tests for payloads, validation, conflict, and navigation state.

## Acceptance Criteria

- All foreign keys are presented with meaningful labels and link to their entities.
- Album Model and logical/release relationships persist in their relationship records and reject invalid/self/duplicate links.
- Protected deletes explain references and preserve records when rejected.
- Filters, sorting, pagination, and open context survive navigation as specified.
- Album is the page's minimum asset-management unit; no independent Photo browse/edit/delete surface is exposed.
- Until Digital Asset Trash is implemented, the UI does not offer the current database-only Album hard-delete behavior.

## Verification

- Run Web client contract tests and focused Backend entity API tests.
- UI-012 supplies the full browser acceptance evidence.

## Risks or Notes

- Any mismatch between UI editable fields and Backend writable fields must be resolved in Specification/API contracts, not patched by silent field omission.
- Read-only Photo evidence selected by a future AI review workflow belongs to `UI-011*` or a later native-client specification, not this task.

## Completion Record

- Added composable Album search/date/rating/Model filters with URL-preserved list context and reviewed batch editing.
- Added readable Album relation selection, duplicate/self prevention, inline Model/Studio creation, and role-aware actions.
- Removed routine Photo presentation and the unsafe database-only Album hard-delete action pending Digital Asset Trash.
- Added focused browser acceptance against disposable authenticated Backend state.
