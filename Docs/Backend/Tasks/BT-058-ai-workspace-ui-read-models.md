# BT-058 — Complete AI Workspace and Work Dispatch UI Read Models

## Task ID

`BT-058` — Status: `Complete`

## Title

Complete Stable AI Workspace and Work Dispatch Read Models for UI Clients

## Related Specification(s)

- UI-011C AI Workspace Review UI.
- UI-011E Admin Album Work Dispatch Console.
- [API Specification](../Specifications/API-Specification.md).
- [Work Dispatch Workflow](../Specifications/Work-Dispatch-Workflow.md).

## Goal

Expose bounded Backend-owned projections so UI clients can render dispatch,
review, Promotion, and retention state without per-row request loops or
client-derived business rules.

## Scope

- Worker-kind catalog and Workspace overview with state counts and allowed actions.
- Paginated Active/History/All Dispatch Group queries with Album, Batch,
  Reservation, Work Item, review, Promotion, closure, and Operation summaries.
- Review queue filters for Album, model configuration, Group, state, and text.
- Review detail with current Album, evidence availability, Promotion history,
  Operations, Issues, lineage, and Backend-permitted actions.
- Stable read-only Promotion history independent of the mutation Preview API.
- Admin authorization, structured validation, pagination, and no sensitive path
  or Token disclosure.

## Out of Scope

- UI components or browser acceptance.
- New review, Promotion, dispatch, or retention state transitions.

## Dependencies

- BT-043 through BT-057.
- BT-053 disposable AI Workspace acceptance fixture.

## Implementation Steps

1. Add repository projections and service-level filter/action validation.
2. Add versioned Admin routes and enrich review detail with traceability.
3. Add projection, authorization, pagination, archived-history, and regression tests.

## Acceptance Criteria

- UI-011C/E can render their primary lists and detail views without deriving
  eligibility, lifecycle, review, Promotion, or release rules.
- Active and History views are globally queryable and paginated.
- Archived Promotion and evidence history remain readable without issuing a
  mutation Preview.
- Responses contain stable identities and public traceability links but no
  claim Token, absolute Album path, or sensitive diagnostics.

## Verification

- Focused repository/service/API contract tests.
- BT-053 AI Workspace workflow readiness and complete Backend regression.

## Completion Record

- Added Admin-only Worker-kind, global Dispatch Group, Workspace overview, and
  read-only Promotion-history endpoints.
- Added bounded review queue filters and enriched review detail with Album,
  configuration, evidence availability, decisions, Promotion, Operation, Issue,
  Group, and rework lineage.
- Verified Active and released Group projections, authorization, pagination,
  traceability, and absolute-path/sensitive-diagnostic redaction in the API
  contract suite.
- Passed the 4-scenario disposable AI Workspace acceptance suite and all 751
  Backend tests on 2026-08-10. Existing ResourceWarnings from test-owned SQLite
  connections remain outside this task's read-model scope.

## Risks or Notes

- Projections may join several workflow tables; all queries must remain bounded
  and indexed/paginated rather than becoming generic database browsing APIs.
