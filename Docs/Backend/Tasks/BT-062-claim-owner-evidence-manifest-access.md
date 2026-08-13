# BT-062 — Claim-Owner Evidence Manifest Access

## Task ID

`BT-062` — Status: `Complete`

## Title

Allow an Active Writer Claim to Prepare Backend-Selected Evidence

## Related Specification(s)

- [API Specification](../Specifications/API-Specification.md), Work Item
  Manifest and opaque Evidence transfer.
- [Authentication](../Specifications/Authentication.md), least-privilege Writer
  Worker boundary.

## Goal

Let the runnable remote AI Worker obtain the Backend-selected Manifest for its
own active claim without granting path selection, directory browsing, another
claim's evidence, or Admin capabilities.

## Scope

- Writer claim-owner authorization for Work Item Manifest create/read.
- Manifest creation after claim while preserving Backend-only selection.
- Wrong, expired, unclaimed, and other-Writer denial evidence.
- Real-HTTP Worker workflow acceptance through `ReadyForReview`.

## Out of Scope

- Caller-selected paths/files/sample membership.
- General Writer evidence browsing or historical Admin evidence access changes.

## Dependencies

- BT-046–049 and MT-009.

## Implementation Steps

1. Add active-claim ownership authorization to the Manifest service.
2. Permit Backend selection in `Claimed` state and expose it through the
   existing versioned Work Item endpoint.
3. Extend API and Worker acceptance tests.

## Acceptance Criteria

- Only Admin or the exact unexpired Writer claim owner can read the Manifest.
- Only the exact active claim owner can request Worker-side preparation.
- The request accepts no path/file/sample input and returns no absolute path.
- The real Worker client reaches `ReadyForReview` through opaque Evidence APIs.

## Verification

- Focused API authorization and Worker runtime tests.
- Backend workflow/readiness regression.

## Risks or Notes

- Claim expiry during preparation produces the existing claim/evidence denial;
  the Worker heartbeat limits this race but does not weaken revalidation.

## Completion Record

- Added claim-owner Manifest authorization and allowed Backend-only selection
  after claim.
- Replaced direct test-side result submission with the actual Worker runtime in
  the disposable HTTP workflow, including temporary Evidence cleanup.
