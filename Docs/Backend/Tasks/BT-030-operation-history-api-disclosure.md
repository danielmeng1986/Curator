# BT-030 — Expose Authorized Operation History Read Models

## Task ID

`BT-030` — Status: `Proposed`

## Title

Expose Authorized Operation History Read Models

## Related Specification(s)

- [Operation Logging](../Specifications/Operation-Logging.md), Role-based summaries and diagnostics.
- [API Contract](../Specifications/API-Contract.md), authorization and safe error handling.

## Goal

Expose durable Operation history through an authorized API read boundary with the required reader, writer, and administrator diagnostic disclosure rules.

## Scope

- Add a versioned Operation list/detail read model and role-based field projection.
- Test public summaries for readers, operational diagnostics for writers where permitted, and sensitive diagnostics denial.

## Out of Scope

- New dashboards or external logging products.

## Dependencies

- `BT-023` — provides durable cross-workflow Operation evidence.

## Implementation Steps

1. Define stable list/detail API shapes and authorization projection.
2. Implement repository/service/API read boundary.
3. Add API contract and workflow disclosure tests.

## Acceptance Criteria

- Unauthorized clients cannot read sensitive diagnostics.
- Permitted roles receive only their specified Operation fields.
- Responses use the common API envelope and durable database records.

## Verification

- Run API, authentication, operations, and workflow-readiness groups.

## Risks or Notes

- Do not expose raw paths, tokens, stack traces, or tool output by default.
