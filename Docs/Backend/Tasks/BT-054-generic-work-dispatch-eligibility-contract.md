# BT-054 — Establish Generic Work Dispatch and Eligibility Contract

## Task ID

`BT-054` — Status: `Ready`

## Title

Establish Album-Exclusive Work Dispatch and Worker Eligibility

## Related Specification(s)

- [Work Dispatch Workflow](../Specifications/Work-Dispatch-Workflow.md).
- [Backend Architecture](../Backend-Architecture.md), Work Dispatch Orchestration.

## Goal

Establish the persistent and service contracts for reusable Admin dispatch
without coupling assignment to Album Status or a particular Worker result schema.

## Scope

- Dispatch Batch, Album Work Reservation, Dispatch Group, Worker-kind adapter,
  eligibility result, version, lifecycle, and history contracts.
- Album-wide active uniqueness across Worker kinds and multi-configuration Work
  Items inside one Album Group.
- Schema/migration, repository/service boundaries, stable read records, and
  foundational invariant tests.

## Out of Scope

- Candidate HTTP preview/execution and UI.
- AI Photo evidence, model execution, review, and Promotion.

## Dependencies

- BT-044 through BT-046.
- Approved [Work Dispatch Workflow](../Specifications/Work-Dispatch-Workflow.md).

## Implementation Steps

1. Add versioned Batch, Group, and active Album Reservation persistence with
   durable released history.
2. Add Worker-kind adapter and eligibility contracts, initially registering
   `album_name_analysis` without embedding its result schema.
3. Add migration repeatability, Album uniqueness race, lifecycle, and
   multi-configuration grouping tests.

## Acceptance Criteria

- At most one active reservation exists for an Album across every Worker kind.
- Several model configurations can belong to one Album-analysis Group without
  creating a second reservation.
- Album Status is unchanged by reservation creation and release.
- Released history remains traceable to Batch, Group, Work Items, actor, and reason.

## Verification

- Migration and repository atomicity tests.
- Service invariant and cross-Worker conflict tests.
- Complete Backend regression.

## Risks or Notes

- Do not generalize dataset result fields into the dispatch tables; adapters own
  their Work Items and evidence.

