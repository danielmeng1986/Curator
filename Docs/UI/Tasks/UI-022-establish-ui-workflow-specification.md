# UI-022 — Establish UI Workflow Specification

## Task ID

`UI-022` — Status: `Complete`

## Title

Establish the Controlling UI Workflow and Recovery Specification

## Related Specification(s)

- [Curator Web UI Specification](../Specification.md)
- [UI Specification](../Specification.md)

## Goal

Define UI readiness as a complete, discoverable, interruption-safe user journey
rather than a one-to-one exposure of Backend functions.

## Scope

- Shared workflow anatomy, state visibility, discoverability, continuity,
  delayed actions, retry, confirmation, accessibility, browser persistence, and
  upgrade/cache behavior.
- Authentication as the first normative reference workflow.
- Required specification and browser evidence for future UI work.

## Out of Scope

- Redesigning the visual system or changing Backend business rules.
- Reimplementing every completed feature workflow in this task.

## Dependencies

- UI-019–021 and BT-060–061 — practical enrollment workflow evidence.
- UI-016–017 — readiness and real-browser acceptance foundations.

## Implementation Steps

1. Extract shared requirements from first-Admin and multi-browser enrollment testing.
2. Publish the controlling UI Specification and connect it to existing UI authority documents.
3. Require interruption, persistence, upgrade, and recovery evidence in future workflow tasks.

## Acceptance Criteria

- The Specification distinguishes Backend capability from UI workflow readiness.
- Every workflow has defined entry, state, next action, persistence, recovery,
  completion, failure, security, and acceptance concerns.
- Authentication documents stable recovery after dialog close, navigation,
  refresh, restart, delayed approval, and client upgrade.
- The UI index, safety criteria, readiness matrix, and task index reference the
  controlling Specification.

## Verification

- Documentation link and task-index review.
- Existing authentication browser acceptance remains the first concrete evidence
  and future workflows adopt the expanded interruption matrix.

## Risks or Notes

- Completed workflows may be functionally Ready under older criteria while
  lacking some newly required interruption evidence. The readiness matrix must
  record those gaps when each workflow is next changed or audited.

## Completion Record

- Added the controlling UI workflow Specification, authentication reference
  lifecycle, persistence/upgrade requirements, and definition of done.
- Linked it from the UI plan, safety acceptance, readiness matrix, task index,
  and project documentation index.
