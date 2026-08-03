# BT-016 — Retire Legacy Backend Entry Points

## Task ID

`BT-016` — Status: `Ready`

## Title

Retire Legacy Backend Entry Points

## Related Specification(s)

- [API Specification](../Specifications/API-Specification.md), supported `/api/v1` surface and versioning sections.
- [Backend Architecture](../Backend-Architecture.md), Current Architecture and Controller / API Layer sections.
- [API Contract](../Specifications/API-Contract.md), supported endpoint and error-contract requirements.

## Goal

Safely remove or disable backend entry points and routes outside the target architecture, leaving the approved active backend surface unambiguous and operational.

## Scope

- Inventory active and legacy backend entry points, handlers, and routes.
- Confirm each legacy candidate is not required by an approved Specification or supported client.
- Remove or disable confirmed legacy-only handlers and entry points.
- Update Backend documentation to identify the active supported surface.
- Verify remaining entry points and routes continue to work.

## Out of Scope

- Changing approved `/api/v1` endpoint behavior, contracts, or supported client capabilities.
- Refactoring active backend workflows beyond changes necessary to detach retired entry points.
- Retiring an entry point with unresolved specification or client-dependency evidence.

## Dependencies

- `BT-003` — the shared `/api/v1` contract identifies the active response boundary to preserve.
- [Backend Architecture](../Backend-Architecture.md) — identifies historical and target backend architecture context.
- [API Specification](../Specifications/API-Specification.md) — controls the approved active API surface.

## Implementation Steps

1. Inventory backend startup modules, routes, documentation references, and known client usage.
2. Classify each candidate as active or legacy using approved Specifications and architecture documentation.
3. Remove or disable only confirmed legacy-only entry points and update documentation references.
4. Run focused startup, route, and regression tests for the remaining active Backend surface.

## Acceptance Criteria

- Each retired entry point or route has documented evidence that it is not required by an approved Specification.
- Confirmed legacy-only handlers and entry points are removed or disabled safely.
- Documentation identifies the active backend entry points and supported API surface unambiguously.
- Remaining supported entry points start successfully and their approved routes continue to work.

## Verification

- Run focused startup and route tests for every remaining active backend entry point.
- Run the applicable `/api/v1` API regression suite after retirement.
- Review documentation links and route references to confirm no retired surface is presented as active.

## Risks or Notes

- Do not infer that a route is obsolete solely from low apparent use; approved Specification and client-dependency checks are required.
- Prefer disabling with a clear migration or removal record when immediate deletion would make recovery or verification difficult.
