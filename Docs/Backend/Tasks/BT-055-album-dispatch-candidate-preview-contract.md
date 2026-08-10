# BT-055 — Implement Album Dispatch Candidate and Preview Contract

## Task ID

`BT-055` — Status: `Complete`

## Title

Implement Filtered Album Dispatch Candidates and Bound Batch Preview

## Related Specification(s)

- [Work Dispatch Workflow](../Specifications/Work-Dispatch-Workflow.md), Candidate and Preview contracts.
- [API Specification](../Specifications/API-Specification.md), Work dispatch contracts.

## Goal

Let an Admin filter arbitrary Albums, understand availability and prior work,
select a bounded set, and preview exactly which Groups and Work Items would be created.

## Scope

- Candidate query reusing Album search, Status, Studio, Model, rating, date, and sort filters.
- Available-by-default plus authorized ineligible/active-work explanations.
- Explicit IDs, current-page, and first-`N` selection; Workspace, Worker kind,
  Dataset schema, and one-or-more model configuration binding.
- Zero-write signed preview Token bound to Album and dependent-resource versions.

## Out of Scope

- Material execution or reservation creation.
- UI implementation.

## Dependencies

- BT-054.
- BT-032 Album query contract and BT-045 model configuration contract.

## Implementation Steps

1. Add candidate repository/read-model query and Worker-adapter eligibility projection.
2. Add bounded selection normalization, consequence calculation, and signed preview service/API.
3. Add filter, authorization, eligibility, expiry, tamper, and zero-write tests.

## Acceptance Criteria

- Active reservations are excluded by default and explainable when explicitly requested.
- Preview identifies exact Albums, Groups, configurations, Work Item counts, warnings, and conflicts.
- Preview changes no Album, reservation, Group, Work Item, or Operation.
- Invalid or unbounded selections return structured `400` outcomes.

## Verification

- Repository filter/read-model tests and API contract tests.
- Preview tamper/expiry/state-binding tests.
- Complete Backend regression.

## Risks or Notes

- “All filtered” always resolves to an explicit bounded server-side set.

## Completion Record

- Extended the Album list read model with dispatch-aware availability, active
  Reservation context, and retained latest/history summary while reusing the
  established search, Status, Studio, Model, rating, date, sort, and pagination
  behavior.
- Added Admin-only `GET /api/v1/work-dispatch/candidates`; the default
  `available` view excludes reserved Albums, while `reserved` and `all` explain
  why an Album cannot be dispatched.
- Added Admin-only `POST /api/v1/work-dispatch/preview` for explicit unique IDs
  or normalized first-`N` selection, bounded to 100 Albums. Preview binds the
  Worker kind, Dataset/schema, Workspace, configurations, Album identities and
  versions, selection/filter semantics, expiry, and initiating Admin Token.
- Preview is zero-write: it creates no Batch, Group, Reservation, Work Item, or
  Operation. A blocked selection receives consequences but no execution Token.
- Added signed Token verification for tamper, expiry, Admin ownership, Album,
  Workspace, configuration, and new-Reservation state; BT-056 will consume this
  validation before atomic execution.
- Verification: 6 focused Service/API tests passed and the complete Backend
  regression passed all 712 tests.
