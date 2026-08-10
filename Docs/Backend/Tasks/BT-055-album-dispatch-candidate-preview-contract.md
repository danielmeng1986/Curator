# BT-055 — Implement Album Dispatch Candidate and Preview Contract

## Task ID

`BT-055` — Status: `Proposed`

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

