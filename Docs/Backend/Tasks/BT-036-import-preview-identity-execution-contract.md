# BT-036 — Complete Import Preview Identity and Execution Contract

## Task ID

`BT-036` — Status: `Complete`

## Title

Bind Import Execution to a Reviewed, Versioned Preview

## Related Specification(s)

- [Import Workflow](../Specifications/Import-Workflow.md), preview, confirmation, execution, and Import Action.
- [Canonical Path Rules](../Specifications/Canonical-Path-Rules.md).
- [Operation Logging](../Specifications/Operation-Logging.md).
- [API Specification](../Specifications/API-Specification.md).

## Goal

Ensure authenticated Import execution can perform only the exact normalized
items, action, source-retention semantics, and source/destination state that the
user reviewed.

## Scope

- Return a signed, short-lived `preview_token` from Import preview.
- Bind normalized identities, canonical destinations, COPY/MOVE/DATABASE_ONLY action, configured roots, and source-state fingerprints.
- Make the versioned execute endpoint accept only the preview token.
- Revalidate source, destination, and database collision state before execution.
- Atomically claim a preview for one execution attempt and reject replay.
- Return structured invalid, expired, stale, and replay `409` outcomes with zero business/filesystem mutation.
- Preserve per-item results, aggregate outcome, Operation identity, and `NeedsRepair` truthfulness after execution starts.

## Out of Scope

- Import UI presentation, owned by `UI-006`.
- New source-discovery adapters or Photo import.
- Client-selected arbitrary archive destinations.

## Dependencies

- `BT-008`, `BT-009`, `BT-014`, and `BT-027` — validation, filesystem execution, canonical paths, and Operation lifecycle.
- `UI-003` disposable filesystem/browser fixtures for later UI acceptance.

## Implementation Steps

1. Define token payload, expiry, source fingerprint, and replay-claim contract in the Import and API specifications.
2. Add signed preview issuance and server-side token verification/revalidation.
3. Add atomic preview claim and route execute exclusively through the reviewed payload.
4. Add service, API, filesystem, stale, tamper, expiry, replay, and zero-side-effect tests.

## Acceptance Criteria

- Preview creates no Album, Operation, snapshot, or filesystem mutation.
- The token binds normalized items and exactly one Import Action; the client cannot substitute items or mode at execute time.
- Changed/missing source, newly occupied destination, database collision, invalid signature, expiry, and replay return structured `409` before production mutation.
- Only one concurrent request can claim a preview; rejected attempts have zero business/filesystem side effects.
- Execution results and durable Operation state match verified per-item outcomes, including `NeedsRepair` after a post-persistence filesystem failure.
- Existing non-HTTP service callers remain compatible while the authenticated API enforces the strict token contract.

## Verification

- Run focused Import service and authenticated API tests.
- Run Import happy-path/failure workflow readiness and complete Backend regression.
- Run `UI-006`/`UI-013` browser workflows after integration.

## Risks or Notes

- Source fingerprinting must be deterministic and must not expose absolute source paths through Reader-visible Operation history.

## Completion Record

- Added signed, expiring Import Preview identity bound to normalized items, Import Action, configuration, canonical destinations, and recursive source metadata.
- Changed authenticated execution to accept only the reviewed token, revalidate state, and atomically claim one attempt.
- Added structured invalid, expired, stale, and replay conflict outcomes before production mutation.
- Preserved direct service-call compatibility and existing truthful Operation/NeedsRepair execution behavior.
- Added filesystem workflow and authenticated API coverage for zero-write Preview, source change, tamper, expiry, execution, and replay.
