# BT-006 — Normalize Backend Read Models

## Task ID

`BT-006` — Status: `Ready`

## Title

Normalize Backend Read Models

## Related Specification(s)

- [Repository Specification](../Specifications/Repository-Specification.md), entities and read-model sections.
- [Backend Architecture](../Backend-Architecture.md), Repository Layer and read-model guidance.

## Goal

Define stable, normalized repository read models for Curator's specified domain entities and migrate service consumers away from raw database row structures.

## Scope

- Define canonical repository read models for Albums, Models, Studios, Photos, Workspaces, and other currently specified domain objects.
- Normalize field names, nullability, identifiers, and value shapes at repository boundaries.
- Update service consumers of affected repository outputs.
- Add focused tests for model shape stability and field normalization.

## Out of Scope

- Adding new domain behavior, API endpoints, or database schema changes.
- Redesigning entities or introducing read models for unspecified future queries.
- Changing response serialization beyond consuming normalized repository results.

## Dependencies

- `BT-005` — repository access must be centralized before repository outputs can become the canonical application boundary.
- [Repository Specification](../Specifications/Repository-Specification.md) — controls required entities, read models, and persistence conventions.

## Implementation Steps

1. Inventory raw database row structures consumed outside repositories for the specified entities.
2. Define canonical read-model structures and normalization rules for each required repository output.
3. Map repository results to canonical models and update service consumers.
4. Add tests that assert exact shapes, normalized fields, and representative null or optional values.

## Acceptance Criteria

- Repositories return predictable canonical read models for all in-scope entities.
- Service consumers no longer rely on raw database rows or database-specific field conventions.
- Read-model fields have stable names, types, and normalized values consistent with the Repository Specification.
- Automated tests detect shape or normalization regressions.

## Verification

- Run focused repository tests for each canonical read model and its normalization cases.
- Run service regression tests for consumers migrated from raw database rows.
- Run the applicable API regression suite to confirm externally observable output remains compatible.

## Risks or Notes

- Add read models only for actual specified entity or consumer needs; do not predesign a broad CQRS layer.
- Preserve domain distinctions between absent values, empty collections, and null values when normalizing fields.
