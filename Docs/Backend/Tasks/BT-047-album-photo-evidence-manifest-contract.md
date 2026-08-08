# BT-047 — Implement Backend-Selected Album Photo Evidence Manifest

## Task ID

`BT-047` — Status: `Proposed`

## Title

Create Stable Album Photo Evidence Manifests without a Photo-Table Dependency

## Related Specification(s)

- UI-011A AI Collection Workspace Specification, Photo evidence contract.
- [API Specification](../Specifications/API-Specification.md), Backend-owned filesystem access.

## Goal

Let the Backend select and freeze a small, auditable set of Album images for an
AI run using reliable Album paths without requiring prior Photo-table import.

## Scope

- `workspace_album_ai_worker_photo` evidence identity and Work Item/Album links.
- Ordered relative filename, size, modification time, content hash, selection
  method, selection time, and Manifest version.
- Backend-only discovery beneath the permanent Album path and configurable sample count.
- Deterministic or explicitly recorded sampling, supported-image filtering,
  symlink/path containment, missing-file, and changed-file detection.

## Out of Scope

- General Photo asset ingestion or browsing.
- Serving image bytes, owned by BT-048.

## Dependencies

- BT-046 Work Item ownership and BT-045 sample-count configuration.
- Approved supported formats, maximum sizes, and sampling policy.

## Implementation Steps

1. Define the immutable Manifest schema and safe Album-directory discovery policy.
2. Implement selection, hashing, persistence, and revalidation services.
3. Add traversal, symlink, replacement, missing-file, and repeatability tests.

## Acceptance Criteria

- A Worker cannot nominate a path or add arbitrary evidence.
- Every evidence item resolves beneath the recorded Album directory and has a stable hash.
- A changed or missing file produces a structured conflict before analysis/result acceptance.
- The Manifest remains inspectable even if source content later becomes unavailable.

## Verification

- Disposable Album filesystem tests covering normal and malicious layouts.
- Repository/API contract tests and complete Backend regression.

## Risks or Notes

- Filename alone is insufficient evidence because files can be replaced; content
  hashing is required for the small sampled set.
