# Canonical Path Rules Specification

## Purpose and scope

This Specification defines the required path-safety behavior for Curator. It applies to path creation, imports, comparisons, validation, repair, and persistence. It does not yet define the exact character-by-character canonicalization algorithm; that remains an Open Question.

The canonical path stored in the database is the intended source of truth for a managed directory.

## Responsibilities

| Layer | Responsibility |
| --- | --- |
| Service | Normalize path components, calculate comparison keys, detect collisions, apply business validation, choose readable deterministic collision names, and give repair guidance. |
| Database | Enforce uniqueness of `canonical_path_key` as the final concurrent-write and consistency safety net. |
| Repair workflow | Prefer safely renaming a real directory that differs due to a correctable naming defect over silently changing the canonical database path. |

Database uniqueness does not replace Service validation. It prevents concurrent writers from bypassing the decision already made by Services.

## Required normalization behavior

Before a managed path is created, compared, imported, repaired, or persisted, the Service must:

1. treat the path as components rather than an opaque string;
2. trim leading and trailing whitespace from every component;
3. normalize Unicode;
4. detect case-insensitive collisions;
5. normalize or reject unsupported path-separator forms according to the final rules;
6. compute an explicit comparison key;
7. check proposed canonical path and comparison key against existing managed paths.

When a later import collides after normalization and a new name is permitted, the Service selects a deterministic readable suffix such as `Name (2)`, then `Name (3)`. It must not silently overwrite an existing directory.

## Decision table

| Condition | Required outcome |
| --- | --- |
| Normalized path and key are unused | Continue with validation and requested workflow. |
| Key conflicts with an existing canonical path | Reject or enter an approved collision/repair workflow; never overwrite. |
| Real directory differs only by a safe correctable defect | Prefer safe rename to the canonical database path; record repair. |
| Real directory conflicts ambiguously | Create/maintain a Manual Conflict and require user choice. |
| Database rejects duplicate `canonical_path_key` after Service validation | Do not claim success; return a concurrent conflict outcome. |

## Validation and error handling

Path-level consistency validation checks canonical-path agreement, directory existence, case conflicts, trailing whitespace, and Unicode-normalization conflicts. Failed validation blocks the dependent action or creates a Repair/Filesystem Issue when tracking is required.

## Operation and snapshot requirements

Material path changes and repairs create Operations. Bulk renames and other hard-to-reverse actions are snapshot candidates. The workflow decides risk through the Snapshot Specification.

## Open Questions

- What exact Unicode normalization form is required?
- Which separators and platform-specific forms are accepted, normalized, or rejected?
- Is case comparison always case-insensitive for all configured archive locations?
- Which components may use collision suffixes, and when must a collision be rejected instead?
- How are existing paths migrated safely before `canonical_path_key` uniqueness is enforced?

## Future extensions

File manifests, sizes, and hashes may provide stronger consistency validation later. They complement, but do not replace, canonical path safety.
