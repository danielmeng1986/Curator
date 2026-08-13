# UI-012 — Add Entity Management Browser Acceptance

## Task ID

`UI-012` — Status: `Complete`

## Title

Add Permanent Entity Management Browser Acceptance

## Related Specification(s)

- [UI Entity Management](../Features/Entity-Management.md).
- [UI Data Interaction Rules](../Data-Interaction-Rules.md).

## Goal

Prove core permanent-entity journeys and relationship safety through the real
UI against disposable Backend state.

## Scope

- Create/edit/search/filter/paginate Album, Model, Studio, and Status records.
- Add/remove Album Models and logical/release relations; verify no routine Photo CRUD surface is exposed.
- Inline creation, validation retention, reference-protected deletion, refresh persistence, and role behavior.

## Out of Scope

- Exhaustively retesting repository validation or Import-created entities.

## Dependencies

- UI-003 and UI-005.

## Implementation Steps

1. Define critical journeys and exact database/API side-effect assertions.
2. Implement Playwright scenarios using stable accessible selectors.
3. Run twice and retain sanitized failure artifacts.

## Acceptance Criteria

- Successful mutations survive refresh and match relationship-table state.
- Invalid, duplicate, self-related, cancelled, and reference-blocked actions preserve prior state.
- Reader cannot mutate even through direct request; Writer sees allowed actions.
- Browser assertions cover visible outcome and durable Backend state.
- The database-only Album hard-delete path is unavailable while Digital Asset Trash is not implemented.

## Verification

- Run entity browser suite twice, Web contract tests, and relevant Backend API regression.

## Risks or Notes

- Tests should assert user-facing labels and roles, not brittle CSS layout details.

## Completion Record

- Added a disposable browser journey covering create, edit, refresh persistence,
  search, filtering, and real second-page navigation across Album, Model,
  Studio, and Status surfaces.
- Proved inline and dedicated relationships: Model and `BELONGS_TO` links are
  added and removed transactionally, duplicate selections are rejected, the
  current Album cannot be selected as its own related release, and cancelling
  the modal causes no durable side effect.
- Proved invalid form drafts remain visible, referenced Model/Studio deletion is
  rejected, referenced Status deletion remains disabled, Reader UI/direct API
  writes are denied, Photo CRUD is absent, and Album hard delete remains absent.
- Corrected the versioned collection adapter to consume
  `meta.pagination.total`, and corrected shared permission handling so it does
  not overwrite a component's Backend-derived business-disabled state.
- The UI-012 suite passed twice from clean disposable roots; Web API/interaction
  contracts and relevant Backend entity/API regression also passed on
  2026-08-11.
