# BT-024 — Verify Authenticated API Workflow Entry Points

## Task ID

`BT-024` — Status: `Complete`

## Title

Verify Authenticated API Workflow Entry Points

## Related Specification(s)

- [Authentication](../Specifications/Authentication.md), Registration and approval workflow, Current authorization model, and Access and error handling sections.
- [API Specification](../Specifications/API-Specification.md), request handling and error behavior sections.
- [API Contract](../Specifications/API-Contract.md), access policy and workflow outcomes sections.
- [Import Workflow](../Specifications/Import-Workflow.md), client and Import Service responsibilities.

## Goal

Verify from a non-UI client perspective that an approved device can enter supported protected Backend workflows through `/api/v1`, while unauthenticated and under-scoped requests are rejected before business work begins.

## Scope

- Exercise device registration, administrator approval, one-time token issuance, and bearer-token use against an in-process loopback API server.
- Exercise representative protected read and material workflow endpoints that are implemented, beginning with import-related operations.
- Assert common envelopes, status/error mapping, scope enforcement, and absence of business side effects after rejected requests.

## Out of Scope

- Starting the Web UI, browser automation, or manually approving a registration through UI screens.
- HTTPS deployment hardening and future refresh-token mechanisms.
- Replacing service-level workflow acceptance scenarios with HTTP-only duplicates.

## Dependencies

- `BT-018` — provides disposable workflow sandbox configuration.
- `BT-013` and `BT-017` — provide authentication and API regression boundaries.
- `BT-019` and `BT-020` — provide supported import workflow outcomes to expose and verify at the API boundary.

## Implementation Steps

1. Configure the ephemeral API server with the disposable workflow sandbox and test-only administrative approval path.
2. Add registration, approval, issuance, and authenticated request helpers that never expose persisted token hashes.
3. Add representative authorized and rejected workflow requests, checking durable side effects only for accepted requests.
4. Add scenarios to a separately runnable API-workflow group.

## Acceptance Criteria

- A device receives no protected workflow access before administrator approval and token issuance.
- Valid bearer tokens with the required scope can invoke supported workflow entry points through the documented API contract.
- Missing, invalid, expired, revoked, or under-scoped tokens are rejected before the protected service changes business state.
- API responses retain the specified envelope, status, and safe error/disclosure behavior without starting a UI.

## Verification

- Run the authenticated API-workflow group against an ephemeral loopback server and disposable resources.
- Run API and authentication regression groups, then the complete suite.

## Risks or Notes

- Registration and administrator approval use loopback-only `/api/auth/*` management endpoints. They deliberately remain outside ordinary bearer-token routes; protected business workflow entry remains `/api/v1`.
