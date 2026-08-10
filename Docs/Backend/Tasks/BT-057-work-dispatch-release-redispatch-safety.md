# BT-057 — Implement Work Dispatch Release and Redispatch Safety

## Task ID

`BT-057` — Status: `Proposed`

## Title

Close Album Work Groups and Safely Release Reservations

## Related Specification(s)

- [Work Dispatch Workflow](../Specifications/Work-Dispatch-Workflow.md), Active reservation and release rules.
- [Workspace Workflow](../Specifications/Workspace-Workflow.md).

## Goal

Allow an Admin to close terminal or abandoned work deliberately, release the
Album reservation, and redispatch later without erasing earlier evidence.

## Scope

- Group cancellation, terminal-state evaluation, explicit abandonment, release
  reason/actor/version, and released-history reads.
- Guards for active claims, retries, review, rework, approval, and pending Promotion.
- New-identity redispatch and Operation/Issue traceability.

## Out of Scope

- Automatic timeout-based abandonment.
- Deleting Batches, Groups, Work Items, results, reviews, or attempts.

## Dependencies

- BT-056, BT-050, and BT-051.

## Implementation Steps

1. Implement permitted-action calculation and versioned Group close/release commands.
2. Add active/history queries and redispatch through a new preview/execution cycle.
3. Add every premature-release, terminal outcome, stale, replay, and history-retention test.

## Acceptance Criteria

- Active execution, review, rework, or Promotion obligations prevent release.
- A permitted release records a reason and Operation and never changes Album Status.
- Redispatch creates new identities while preserving prior Batch/Group evidence.
- An Album becomes a default dispatch candidate only after committed release.

## Verification

- Generated release guard tests and API authorization/version tests.
- End-to-end release/redispatch traceability tests.
- Complete Backend regression.

## Risks or Notes

- Individual Work Item terminal states are insufficient to infer Group release.

