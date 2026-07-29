# Canonical Path Rules Specification

## Purpose and scope

This Specification defines required path-safety behavior for Curator path creation, imports, comparisons, validation, repair, renames, and persistence. It does not define every character-level component rule; those remain open where explicitly noted.

A canonical path is the computed source of truth for a managed Album directory. `album.path` stores that canonical path value; it is not an independently editable path string.

## Responsibilities

| Layer | Responsibility |
| --- | --- |
| Service | Derive canonical paths from Album metadata, normalize components, calculate comparison keys, detect collisions, apply business validation before persistence, choose permitted Album collision names, and give repair guidance. |
| Database | Enforce uniqueness of `canonical_path_key` as the final concurrent-write and consistency safety net. |
| Repair workflow | Prefer safely renaming a real directory that differs due to a safe, unambiguous naming defect over silently changing the canonical database path. |

Database uniqueness does not replace Service validation. It protects against concurrent writers or other persistence paths after the Service has made the business decision.

## Canonicalization and comparison

Before a managed path is created, compared, imported, repaired, or persisted, the Service must treat it as components rather than an opaque string and must:

1. trim leading and trailing whitespace from every component;
2. normalize every component to Unicode NFC;
3. normalize separators to `/`;
4. apply case-insensitive comparison across the Curator archive, regardless of host platform;
5. normalize or reject unsupported path forms according to the component rules;
6. derive a comparison key from the canonicalized path; and
7. check the proposed canonical path and comparison key against existing managed paths.

The comparison key is an internal normalized key derived from the canonical path. It is used for equality checks, collision detection, and uniqueness enforcement. `canonical_path_key` persists this key; it is not a user-editable alternative path.

## Collision handling

Only the Album component may receive an automatic collision suffix. When an Album name collision is permitted, the Service selects a deterministic, readable suffix such as `Name (2)`, then `Name (3)`, and recomputes and validates the resulting canonical path.

Model, Studio, and every other non-Album component must not be auto-suffixed. A collision in one of those components must be rejected or escalated for manual confirmation. No collision workflow may silently overwrite an existing directory.

## Rename and recomputation workflow

Canonical paths are computed from Album metadata and must be recomputed, never patched in place. For any metadata change that affects an Album path, the Service must:

1. update the Album name or other relevant metadata in the proposed state;
2. recompute the canonical path and comparison key from that metadata;
3. validate the recomputed path, including collision handling; and
4. apply the filesystem rename and persist the updated Album state only after validation succeeds.

The rename is a transaction-like workflow: it records the Operation, coordinates database and filesystem stages, and leaves an actionable repair state if either stage cannot complete. It must keep the intended database state and filesystem state aligned without silently overwriting or deleting data.

## Decision table

| Condition | Required outcome |
| --- | --- |
| Canonical path and comparison key are unused | Continue with validation and requested workflow. |
| Album-name collision where suffixing is permitted | Select the next deterministic Album suffix, then recompute and validate. |
| Non-Album component collision | Reject or require manual confirmation; do not auto-suffix. |
| Comparison key conflicts with an existing canonical path | Reject or enter an approved collision/repair workflow; never overwrite. |
| Real directory differs only by a safe, unambiguous naming defect | Prefer safe rename to the canonical database path; record repair. A trailing-space difference is one illustration. |
| Real directory conflicts ambiguously | Create or maintain a Manual Conflict and require user choice. |
| Database rejects duplicate `canonical_path_key` after Service validation | Do not claim success; return a concurrent conflict outcome. |

## Validation and error handling

Service-layer validation always occurs before persistence. Path-level consistency validation checks canonical-path agreement, directory existence, case conflicts, trailing whitespace, and Unicode-normalization conflicts. Failed validation blocks the dependent action or creates a Repair/Filesystem Issue when tracking is required.

## Operation and snapshot requirements

Material path changes and repairs create Operations. Bulk renames and other hard-to-reverse actions are snapshot candidates. The workflow decides risk through the Snapshot Specification.

## Migration

The current archive has already been scanned and repaired externally; this Specification does not imply unresolved migration work for its present state. For future data, `canonical_path_key` uniqueness must be introduced safely. Existing databases must be migrated only after conflicts have been identified and resolved, so the unique constraint can be enabled without data loss or silent renames.

## Open Questions

- What remaining Album-metadata changes affect the canonical-path lifecycle, and where is the complete rename/recomputation flow specified for each of them?
- Which unsupported platform-specific path forms must be rejected rather than normalized?
- What exact character-level component canonicalization rules apply beyond the normalization rules in this Specification?

## Future extensions

File manifests, sizes, and hashes may provide stronger consistency validation later. They complement, but do not replace, canonical path safety.
