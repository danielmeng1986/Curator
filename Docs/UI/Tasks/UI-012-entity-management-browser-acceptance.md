# UI-012 — Add Entity Management Browser Acceptance

## Task ID

`UI-012` — Status: `Proposed`

## Title

Add Permanent Entity Management Browser Acceptance

## Related Specification(s)

- [UI Entity Management](../03_Entity_Management.md).
- [UI Data Interaction Rules](../02_Data_Interaction_Rules.md).

## Goal

Prove core permanent-entity journeys and relationship safety through the real
UI against disposable Backend state.

## Scope

- Create/edit/search/filter/paginate Album, Model, Studio, and Status records.
- Add/remove Album Models and logical/release relations; inspect/delete Photo records.
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

## Verification

- Run entity browser suite twice, Web contract tests, and relevant Backend API regression.

## Risks or Notes

- Tests should assert user-facing labels and roles, not brittle CSS layout details.

