# BT-048 — Implement Controlled AI Photo Evidence Transfer API

## Task ID

`BT-048` — Status: `Proposed`

## Title

Stream Manifest-Bound Photo Evidence to AI Workers and Administrators

## Related Specification(s)

- UI-011A AI Collection Workspace Specification, remote Worker and review evidence.
- [Authentication](../Specifications/Authentication.md).
- [API Contract](../Specifications/API-Contract.md).

## Goal

Transfer the small Manifest-selected image set across the LAN through REST
without exposing arbitrary filesystem access or absolute paths.

## Scope

- Evidence-metadata and content endpoints addressed only by opaque evidence identity.
- Writer access limited to a currently claimed Work Item; Admin access limited
  to review/audit needs.
- Path revalidation, hash/size validation, MIME allow-list, response limits,
  streaming, cancellation, and safe cache/download headers.
- Optional bounded review thumbnail/preview representation.

## Out of Scope

- Arbitrary Album file download, directory listing, upload, or Photo browsing.
- WAN/CDN delivery and image transformation infrastructure.

## Dependencies

- BT-047 Manifest and BT-046 Worker claim ownership.
- Deployment decision for LAN bind/firewall and maximum transfer limits.

## Implementation Steps

1. Define evidence metadata/content response contracts and authorization rules.
2. Implement safe file resolution and bounded streaming/preview delivery.
3. Add role, claim, traversal, changed-content, MIME, disconnect, and redaction tests.

## Acceptance Criteria

- No request parameter is interpreted as an absolute or caller-selected relative path.
- Writers cannot read evidence outside their active claim.
- Hash or containment mismatch returns a structured error and no content.
- Logs, errors, and JSON metadata never disclose the Album absolute path.

## Verification

- Disposable cross-process Worker download tests over loopback/LAN-equivalent REST.
- Security-negative API tests and complete Backend regression.

## Risks or Notes

- Eight bounded images per Album is acceptable for the initial LAN workflow;
  transport metrics should be retained before expanding sample sizes.
