# BT-004 — Separate Transport Logic from Application Logic

## Task ID

`BT-004` — Status: `Complete`

## Title

Separate Transport Logic from Application Logic

## Related Specification(s)

- [API Specification](../Specifications/API-Specification.md), request handling and HTTP response sections.
- [API Contract](../Specifications/API-Contract.md), status mapping and workflow outcome sections.
- [Backend Architecture](../Backend-Architecture.md), Controller / API Layer and Domain Service Layer sections.

## Goal

Refactor backend HTTP handlers into transport adapters while moving workflow and domain decisions into application services without changing endpoint behavior.

## Scope

- Limit HTTP handlers to route dispatch, request parsing, transport-shape validation, and HTTP status translation.
- Extract existing workflow and business-rule logic into focused application service boundaries.
- Update handler tests and add focused service tests for extracted behavior.

## Out of Scope

- Changing endpoint routes, request or response contracts, or business rules.
- Moving direct persistence access into repositories; that is covered by a separate task.
- Adding new workflows or API capabilities.

## Dependencies

- `BT-003` — shared API serialization must be available for consistent handler response translation.
- [Backend Architecture](../Backend-Architecture.md) — defines the controller and service responsibilities to preserve.

## Implementation Steps

1. Identify workflow and domain decisions embedded in active backend HTTP handlers.
2. Define focused application service operations around the existing endpoint use cases.
3. Move workflow logic to services and reduce handlers to transport adaptation.
4. Update handler and service tests to prove behavior remains stable.

## Acceptance Criteria

- HTTP handlers perform only transport responsibilities and call the appropriate service operation.
- Workflow and domain rules no longer reside in controllers.
- Existing endpoint status codes, response contracts, and observable behavior remain unchanged.
- Extracted service behavior has focused automated test coverage.

## Verification

- Run focused handler tests for request parsing, route dispatch, and status translation.
- Run service tests for each extracted workflow or domain-rule outcome.
- Run the applicable API regression suite to confirm endpoint compatibility.

## Risks or Notes

- Preserve the existing transaction and recovery boundaries while extracting services; do not duplicate business decisions between handlers and services.
- Persistence-boundary refactoring is intentionally deferred to its dedicated repository task.
