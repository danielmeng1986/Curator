# MT-006 — Establish UI Workflow Acceptance Testing

## Task ID

`MT-006` — Status: `Proposed`

## Title

Establish UI Workflow Acceptance Testing

## Related Specification(s)

- [UI Safety and Acceptance](../../UI/06_Safety_and_Acceptance.md).
- [Testing Strategy](../../Backend/Testing-Strategy.md), Workflow Tests and API Contract Tests.
- [Workflow Readiness Matrix](../../Backend/Workflow-Readiness-Matrix.md).

## Goal

Add browser-level workflow acceptance tests for the migrated Web client while
retaining Backend workflow tests as the durable business-rule foundation.

## Scope

- Test approved-device access, authenticated import, Workspace lifecycle, Repair/Issue visibility, and safe error presentation.
- Run against disposable Backend/database/filesystem resources.
- Publish a UI readiness matrix that links each UI scenario to its Backend workflow evidence.

## Out of Scope

- Re-testing every Service rule through the browser.
- Performance, visual-polish, accessibility, and deployment certification beyond specified acceptance scope.

## Dependencies

- `MT-002` and `MT-003` — migrated Backend and Web client.
- `MT-004` only for AI-result UI workflows.
- `BT-030` for Operation-history UI views; `BT-031` for promotion UI flows.

## Implementation Steps

1. Choose a browser automation boundary and disposable test composition root.
2. Implement critical-path scenarios against `/api/v1` with explicit durable assertions.
3. Add the UI gate beside Backend `workflow-readiness`.

## Acceptance Criteria

- UI tests never use production database, archive, token, or output paths.
- Rejected actions visibly preserve zero business side effects.
- Each UI workflow links to a passing Backend workflow or an explicit readiness gap.

## Verification

- Run browser workflow tests twice from clean fixtures.
- Run Backend workflow-readiness and full regression afterward.

## Risks or Notes

- UI tests prove client integration; they do not replace service-level safety tests.
