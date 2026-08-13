# UI-004C — Add Token Connection Lifecycle UI

## Task ID

`UI-004C` — Status: `Complete`

## Title

Add Device Connection and Token Lifecycle UI

## Related Specification(s)

- [Authentication](../../Backend/Specifications/Authentication.md), Token and renewal lifecycle.
- [UI Foundation](../Foundation-and-Navigation.md).

## Goal

Turn the current connection dialog into a complete role-aware device connection
experience for active, expiring, expired, revoked, and replacement Tokens.

## Scope

- Connect, validate, replace, and disconnect an approved device Token.
- Display device name, role, scopes, expiration, and renewal state.
- Renewal request and approved replacement handling.
- Route/action gating and safe local browser storage.

## Out of Scope

- Administrator approval UI, handled by UI-010A.
- Browser-profile encryption guarantees not provided by the runtime.

## Dependencies

- UI-002 — shared permission and authentication states.
- Required authenticated principal/token metadata and renewal API contracts.

## Implementation Steps

1. Define connection state, local storage, disconnect, and replacement behavior.
2. Add current-principal metadata and renewal integration where missing, then adapt the UI shell.
3. Test active, insufficient-scope, expiring, expired, revoked, invalid, and replaced Token cases.

## Acceptance Criteria

- The UI shows the authenticated device and effective authorization without displaying Token plaintext.
- Expired/revoked Tokens stop protected actions and give an appropriate recovery path.
- Disconnect removes local credentials and protected views immediately.
- Replacement succeeds before the old Token is removed locally; failed replacement retains a still-valid old connection.

## Verification

- Extend client contract tests and add browser lifecycle scenarios using UI-003 fixtures.
- Run Backend authentication and API-contract regressions.

## Risks or Notes

- Client-side route hiding never substitutes for Backend scope enforcement.

## Completion Record

- Added `/api/v1/auth/me` with safe device, role, scope, Token lifetime, and
  pending-renewal metadata plus an authenticated renewal-request endpoint.
- Rebuilt connection handling so a candidate Token is validated before current
  browser settings change; disconnect removes local credentials immediately.
- Added role-aware navigation/action presentation and direct-route rejection,
  while retaining Backend enforcement as the authority.
- Added browser acceptance for active metadata, renewal Pending state, failed
  and successful replacement, Reader gating, disconnect, expiry, and revocation.
