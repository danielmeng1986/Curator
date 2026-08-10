# BT-047 — Implement Backend-Selected Album Photo Evidence Manifest

## Task ID

`BT-047` — Status: `Complete`

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
- Approved policy: configuration `sample_count` defaults to 8; supported files
  are JPG/JPEG, PNG, and WebP up to 32 MiB. Selection prioritizes the arithmetic
  mean-size ±30 percent band, samples it deterministically by relative path, and
  fills a short band with images nearest the mean. Fewer eligible images than
  `sample_count` is an Issue-producing conflict, not a degraded AI run.

## Completion Record

- Added migration `0008_ai_photo_evidence_manifest.sql` with one immutable
  Manifest per Work Item and ordered `workspace_album_ai_worker_photo` evidence
  retaining relative path, size, nanosecond modification time, SHA-256, and MIME.
- Implemented recursive Backend-only discovery for signature-validated
  JPG/JPEG, PNG, and WebP files up to 32 MiB. Symlinks, traversal, unsupported,
  oversized, and unreadable inputs cannot enter a Manifest.
- Implemented the approved arithmetic-mean ±30 percent priority pool,
  deterministic relative-path sampling, and nearest-mean fallback. The model
  configuration snapshot supplies the run-specific sample count.
- Zero/missing images and insufficient eligible images create a durable Issue
  and structured conflict without a Manifest. Selected content is revalidated
  by containment, size, mtime, and hash before later use.
- Added Admin-only Work Item Manifest create/read APIs. Responses retain opaque
  evidence identity and relative metadata without absolute Album paths; the
  permanent `photo` table remains untouched.
- Verification: 6 focused migration/service/API tests passed and the complete
  Backend regression passed all 723 tests.
