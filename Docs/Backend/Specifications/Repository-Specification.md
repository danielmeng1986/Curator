# Repository Specification

## Purpose and scope

This Specification defines the persistence boundary used by Backend Services. A Repository expresses Curator persistence intent and returns domain entities or query-specific read models. It hides SQL, database connections, database row formats, and engine-specific behavior.

It does not prescribe repository classes, interfaces, ORM usage, SQL, schema syntax, or database libraries.

## Responsibilities

| Layer | Responsibility |
| --- | --- |
| Service | Business validation, transaction intent, lifecycle permissions, and workflow decisions. |
| Repository contract | Domain-oriented persistence operations required by Services. |
| SQLite implementation | Current implementation of the contract against SQLite. |
| Future PostgreSQL implementation | Later implementation of the same needed contract against PostgreSQL. |

Services depend on repository contracts, never a SQLite or PostgreSQL implementation. Repositories do not decide business rules, authorize clients, or interpret HTTP requests.

## Required repository behaviors

- Retrieve and persist permanent entities, workspace data, status lookups, Operation history, and Issues only through Backend-owned contracts.
- Participate in a Service-defined transaction boundary.
- Preserve hard database constraints and report persistence conflicts to Services in a form that does not leak engine-specific details to clients.
- Return domain entities for ordinary CRUD needs.
- Return a dedicated read model only when a query naturally needs aggregation, joins, filtering, pagination, statistics, or presentation-oriented fields.

## Read-model contract

Read models are Repository result structures for API/display consumption; they are not a separate CQRS architecture.

Likely early read models are Album List, Workspace Review, Import Preview, Repair Result View, Studio Overview, and Validation Dashboard. Simple lookups, such as a Status dropdown, should return only the data needed by that lookup.

Each read model must specify its source entities, included derived values, filtering/sorting inputs, pagination behavior where applicable, and freshness/consistency expectations in the owning workflow or API Specification.

## Validity and error handling

| Situation | Repository behavior |
| --- | --- |
| Record does not exist | Return a not-found outcome to the Service. |
| Unique, foreign-key, required-value, or join uniqueness constraint fails | Return an integrity-conflict outcome; never silently weaken the constraint. |
| Transaction cannot commit | Report failure so the Service can return an unsuccessful operation outcome. |
| Engine-specific error | Translate to a persistence failure without exposing SQL or driver details outside the Backend. |

## Identity and invariants

Business entities use UUID as their stable external identity. Small stable lookup tables such as `status` may retain an integer identifier. Repositories must not encourage API clients or Services to depend on general business integer IDs.

The database is the final enforcer of UUID, foreign-key, required-value, join-uniqueness, and `canonical_path_key` uniqueness constraints. Repositories must preserve that enforcement rather than pre-checking and then bypassing it.

## Open Questions

- Which exact query inputs and result fields belong to each first read model?
- Which Repository contract is responsible for each cross-entity promotion and repair query?
- How should query consistency be expressed for long-running scans and paginated results?

## Future extensions

A PostgreSQL implementation may be added once the Architecture threshold for migration is met. It must satisfy the same behavioral contract and UUID identity rules; it must not require Services or clients to learn database-specific behavior.
