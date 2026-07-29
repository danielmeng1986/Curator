# Repository Specification

## Purpose and scope

This Specification defines the persistence boundary used by Backend Services. A Repository expresses Curator persistence intent in support of business workflows and returns domain entities or workflow-specific read models. It hides SQL, database connections, database row formats, and engine-specific behavior.

Repository contracts are organized around business capabilities and workflow operations, not individual database tables. They support such operations as Import Preview, AI Review, Validation, Repair, and Promotion rather than exposing generic CRUD methods for every table.

It does not prescribe repository classes, interfaces, ORM usage, SQL, schema syntax, or database libraries.

## Responsibilities

| Layer | Responsibility |
| --- | --- |
| Service | Business validation, transaction intent, lifecycle permissions, and workflow decisions. |
| Repository contract | Workflow-oriented persistence operations and Read Models required by Services. |
| SQLite implementation | Current implementation of the contract against SQLite. |
| Future PostgreSQL implementation | Later implementation of the same needed contract against PostgreSQL. |

Services depend on repository contracts, never a SQLite or PostgreSQL implementation. Repositories do not decide business rules, authorize clients, interpret HTTP requests, or define lifecycle policy.

The Workspace Workflow Specification defines lifecycle states and permitted workflow actions. Repository contracts support those actions: for example, an AI Review contract must respect the Review-stage editing contract, and a Promotion contract must support the validation and closure rules owned by the Service.

## Required repository behaviors

- Retrieve and persist permanent entities, workspace data, status lookups, Operation history, and Issues only through Backend-owned contracts when required by a business capability.
- Participate in a Service-defined transaction boundary.
- Preserve hard database constraints and report persistence conflicts to Services in a form that does not leak engine-specific details to clients.
- Provide write and lookup operations that a Service needs to perform a defined workflow operation; do not expose table CRUD merely because a table exists.
- Return domain entities for bounded domain operations where the workflow does not require a projection.
- Return a dedicated Read Model for workflow screens and API use cases that need aggregation, joins, filtering, pagination, statistics, or presentation-oriented fields.

## Workflow-oriented Read Models

Read Models are Repository result structures for API/display consumption; they are not a separate CQRS architecture. They are workflow-oriented projections, not entity projections or representations of individual database tables. Every major workflow must define the Read Model or Read Models needed by its screens and API use cases.

Representative workflow-owned Read Models include:

| Read Model | Intended workflow or UI | Typical source entities | Typical derived fields |
| --- | --- | --- | --- |
| `AlbumImportPreviewReadModel` | Import Preview | imported album workspace records, import batch/context, validation outcomes | preview summary, duplicate/conflict indicators, validation counts |
| `AlbumListReadModel` | Album List | albums, status lookups, relevant aggregate relationships | display status, aggregate counts, sortable display values |
| `ValidationIssueReadModel` | Validation | workspace or production records, Issues, validation outcomes | severity summary, affected-record context, resolution state |
| `AiAlbumReviewReadModel` | AI Review | AI album workspace records, raw AI output, reviewer selections, validation outcomes | selected candidate values, review readiness, approval state |
| `RepairCandidateReadModel` | Repair | candidate records, detected conflicts or Issues, repair analysis | repair rationale, confidence or risk indicators, proposed action |

The listed source entities and derived fields are representative, not a schema commitment. The owning workflow specification must define the actual contract.

Each Read Model must be documented in its owning workflow or API Specification with:

- source entities;
- derived fields;
- filtering inputs;
- sorting behavior;
- pagination behavior;
- consistency expectations; and
- intended workflow or UI.

Simple lookups, such as a Status dropdown, should return only the data needed by that workflow.

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

- Which Read Models, including their inputs, fields, sorting, pagination, and consistency expectations, are required by each workflow?
- Which workflow-oriented Repository contracts are required for Import Preview, AI Review, Validation, Repair, Promotion, and other cross-entity operations?
- How should each workflow express consistency expectations for long-running scans and paginated Read Models?

## Future extensions

A PostgreSQL implementation may be added once the Architecture threshold for migration is met. It must satisfy the same behavioral contract and UUID identity rules; it must not require Services or clients to learn database-specific behavior.
