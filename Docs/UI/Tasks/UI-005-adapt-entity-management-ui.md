# UI-005 — Adapt Permanent Entity Management UI

## Task ID

`UI-005` — Status: `Proposed`

## Title

Adapt Permanent Entity Management to the Supported API

## Related Specification(s)

- [UI Data Interaction Rules](../02_Data_Interaction_Rules.md).
- [UI Entity Management](../03_Entity_Management.md).
- [API Specification](../../Backend/Specifications/API-Specification.md).

## Goal

Complete and normalize Album, Model, Studio, Status, Photo, and relationship
management against authenticated `/api/v1` contracts.

## Scope

- Lists, search, filters, sorting, pagination, create, edit, and protected delete.
- Album–Model and Album–Album relationships inside Album detail.
- Photo record visibility/deletion and readable foreign-key labels.
- Inline Model/Studio creation where specified, role-aware actions, validation, and retained drafts.

## Out of Scope

- Import, Workspace, Issue/Repair, and raw relationship-table screens.
- Backend business-rule changes not required by the approved UI contract.

## Dependencies

- UI-001 and UI-002.
- Supported canonical read/write models for each exposed entity surface.

## Implementation Steps

1. Audit current pages against UI field/editability and API contracts.
2. Close behavior and usability gaps by entity, preserving relationship boundaries.
3. Add client contract tests for payloads, validation, conflict, and navigation state.

## Acceptance Criteria

- All foreign keys are presented with meaningful labels and link to their entities.
- Album Model and logical/release relationships persist in their relationship records and reject invalid/self/duplicate links.
- Protected deletes explain references and preserve records when rejected.
- Filters, sorting, pagination, and open context survive navigation as specified.

## Verification

- Run Web client contract tests and focused Backend entity API tests.
- UI-012 supplies the full browser acceptance evidence.

## Risks or Notes

- Any mismatch between UI editable fields and Backend writable fields must be resolved in Specification/API contracts, not patched by silent field omission.

