# Curator Backend Architecture

## Purpose and scope

This document designs the next generation of the Curator Backend before implementation begins. It is an incremental refactoring target for the existing local Python backend, not a proposal to replace Curator's domain model, UI, SQLite database, or local-first deployment model.

Curator Backend owns the database. The current static Web UI, a future Web UI (which may use React, Next.js, or another framework), the AI Worker, CLI tools, and any future client communicate with the Backend through its API; they never open `Curator.db`, issue SQL, or bypass the Service layer. The Backend owns validation, business rules, transaction boundaries, persistence, audit logging, and recovery-oriented operations.

The design deliberately favors a small number of explicit modules over frameworks, dependency-injection containers, generic CRUD engines, or a separate service for every entity. Curator is maintained by one developer, so each abstraction must address a current source of coupling.

## 1. Architecture Principles

These principles are the foundation for all Curator Backend work. They apply to future Specifications and Implementation work unless an Architecture Decision Record explicitly changes them.

- **Backend owns the database.** The Backend is the single owner of database access, writes, transactions, persistence rules, and schema evolution.
- **Clients never access the database directly.** The Web UI, AI Worker, CLI tools, and local tools request Backend operations; they do not open `Curator.db`, run SQL, or bypass validation.
- **Repository hides persistence.** Repositories are the persistence boundary. They hide database-specific queries, rows, and engine behavior from the application layer.
- **Services own business rules.** Validation, workflow decisions, transaction boundaries, and multi-resource coordination belong to Services, independent of the client that initiated the work.
- **Controllers translate HTTP.** HTTP Controllers are adapters: they translate requests to application operations and results to HTTP responses. They do not contain SQL or business workflows.
- **Repositories translate persistence.** A repository translates application persistence needs to the selected database implementation and translates persisted results back to application records.
- **Business logic must never depend on SQL.** Services express Curator intent and rules, not tables, SQL syntax, or SQLite connection behavior.
- **Incremental evolution over large rewrites.** Improve one bounded workflow at a time while preserving working behavior and recovery options.
- **Local-first architecture.** Curator remains a local application by default. Future clients use Backend boundaries without changing this ownership model.
- **REST is the external write boundary.** Out-of-process clients use the versioned HTTP REST API. In particular, the Windows AI Worker on the local network always uses this API and never calls the database or Service layer in-process.
- **Hard integrity and business meaning are complementary.** The database prevents invalid persistent states and race-condition bypasses; Services interpret business meaning, normalize paths, explain errors, and guide repair.
- **Simplicity over enterprise complexity.** New abstractions must remove an observed coupling, duplication, or testing obstacle. Curator does not adopt patterns simply because they are common in larger systems.

## 2. Architecture Decision Records

Important long-lived architectural choices should be documented as Architecture Decision Records (ADRs) in:

```text
Docs/
  Backend/
    ADR/
```

This document defines the overall Backend boundaries and principles. An ADR records a specific decision, its context, alternatives, and consequences after that decision is made. ADRs should be added before implementation when a change affects these boundaries or establishes a durable rule.

Likely ADR topics include Backend database ownership, the Repository pattern, REST as the write entry point for external clients, retaining SQLite as the current implementation, and the eventual PostgreSQL migration approach. ADRs do not replace this Architecture document; they preserve the reasoning behind important decisions over time.

## 3. Current Architecture

### Current `server.py` responsibilities

The current implementation is centred on two standalone HTTP-server modules:

- `workspace/curator_base_app/server.py` supports the earlier Normalize, Import, and Workspace Album pages.
- `tools/web_ui/server.py` is the newer, broader Web UI backend for permanent Albums, Models, Studios, Statuses, Photos, Workspace Albums, direct import, backups, and rollback.

Both modules use Python's standard-library HTTP server and SQLite directly. The newer server is the practical reference for the current full UI; the earlier server is historical context rather than a workflow-migration requirement.

`workspace/curator_base_app` is currently disabled and is not started before the Backend migration is complete. Its routes and workflows are not migration requirements. It remains in the repository only as historical reference until the new Backend is verified and its legacy entry point is formally retired.

In these modules, one file currently performs all of the following:

- Starts the HTTP server, serves static files, parses URLs and JSON, routes HTTP verbs, and creates HTTP responses.
- Loads local configuration and exposes configuration-derived paths.
- Opens SQLite connections and configures SQLite behavior such as foreign keys and WAL mode.
- Defines and executes SQL for reads, CRUD operations, filtering, pagination, relationship changes, and workspace batch edits.
- Validates some request data and enforces rules such as allowed editable fields, duplicate checks, reference checks, and import-path checks.
- Coordinates multi-table Album, `album_model`, `album_relation`, and Photo operations with transactions.
- Parses source folder names, computes archive paths, creates or finds Models and Studios, and coordinates database writes with copy/move filesystem operations.
- Creates, lists, retains, deletes, and restores SQLite snapshots; runs a daily backup thread; writes JSONL change, backup, and rollback logs.

### Concerns currently mixed together

The current source mixes transport, application workflow, persistence, infrastructure, and operational concerns in individual handler methods. For example, an import endpoint can read HTTP input, decide naming/path rules, query and create several entities, commit a transaction, copy files, compensate for a failure, write a log entry, and format an HTTP result. Album edit endpoints similarly combine request parsing, relationship replacement rules, SQL statements, transaction control, and response formatting.

This mixing has already produced duplication between the two server modules: configuration loading, connection creation, backup catalog logic, rollback behavior, logging, import parsing, and SQL conventions exist in more than one place. SQL is also distributed across route handlers, which makes the database contract difficult to locate and protect when clients or schema details evolve.

### Why the current structure will become difficult to maintain

The current design works for a local UI, but the following changes increase the cost of every new feature:

- Adding another Web UI, the AI Worker, or CLI tools would either duplicate business rules in each client or add more routes to an already broad handler.
- Rules can become inconsistent because separate endpoints independently decide validation, duplicate behavior, timestamps, logging, and transaction scope.
- Database changes require finding SQL embedded throughout transport code. Testing a rule requires constructing HTTP requests instead of invoking a focused operation.
- SQLite-specific details (`sqlite3.Row`, PRAGMA statements, `lastrowid`, backup APIs, and SQL syntax) leak into application behavior, making a future PostgreSQL migration unnecessarily wide.
- Import combines a database transaction with filesystem work. That cannot be made fully atomic across both resources, so its preparation, execution, compensation, and audit behavior need one explicit owner.
- Recovery and backup behavior is important operational logic, but it currently competes for space with ordinary HTTP routing and CRUD behavior.

None of these findings require a rewrite. They identify boundaries that already exist in behavior but not yet in the code structure.

## 4. Design Goals

1. **Single responsibility.** A module should have one reason to change: HTTP protocol, a use case, persistence mapping, database connection mechanics, or configuration.
2. **Separation of concerns.** Controllers translate HTTP. Services own workflows and rules. Repositories persist and retrieve. Database code owns engine-specific connections and transactions.
3. **Database independence.** Upper layers use repository contracts and domain-oriented records, not SQLite connection objects or SQL syntax.
4. **Multiple clients.** The same Backend use cases support the Web UI, AI Worker, and CLI tools. External clients use the versioned REST API; no client accesses the database directly.
5. **PostgreSQL readiness.** SQLite remains the current implementation. A later PostgreSQL implementation replaces the database/repository wiring, not controllers or business rules.
6. **Preserve the current model and workflow.** `model`, `studio`, `album`, `photo`, `album_model`, `album_relation`, `status`, and `workspace_album` retain their current concepts and relationships. This architecture does not redesign them.
7. **Safe incremental delivery.** Move one use case at a time behind a tested boundary, retaining existing routes and behavior until replacements are verified.
8. **Appropriate simplicity.** Prefer concrete repositories and small services. Do not introduce microservices, an ORM solely for abstraction, event buses, CQRS infrastructure, or a framework migration unless a real later need justifies it.

## 5. Proposed Backend Architecture

The Backend is a modular monolith: one local process, one API, one database owner, and clear internal layers. Dependencies point inward:

```text
Clients (Web UI / AI Worker / CLI)
        -> REST API adapter
        -> Domain Service
        -> Repository
        -> Database implementation

Configuration is read at startup and supplied to the layers that need it.
```

Filesystem copying/moving, JSONL audit logs, backup storage, and scheduled work are infrastructure collaborators used by services. They are not extra domain layers. Small interfaces are useful only where alternate implementations or safe test doubles are meaningful, such as filesystem operations and snapshot storage.

### Controller / API Layer

Controllers are HTTP adapters, not the application itself. Their responsibility is to:

- Match a route and HTTP method.
- Parse and validate transport shape: JSON syntax, required route IDs, query-string types, pagination bounds, and request DTO structure.
- Call exactly the appropriate service operation.
- Translate known service outcomes into stable HTTP status codes and response DTOs.
- Avoid SQL, direct database connections, filesystem mutation, transaction control, and domain decision-making.

Controllers should be organised by API capability rather than one class per SQL table. A Controller may combine service results into an API response, but it must not recreate service rules.

REST under `/api/v1` is the shared client adapter for the Web UI, Windows AI Worker, CLI tools, and every future client. The Windows AI Worker always uses that HTTP REST API. If a local command runner is introduced, it is a Backend-operated adapter and does not create a second client persistence path. Every adapter reaches Services; no adapter reaches repositories or SQLite directly.

### Domain Service Layer

Services implement Curator use cases and own their business rules. They receive validated command/query objects, coordinate repositories and infrastructure, select transaction boundaries, and return application results independent of HTTP.

Examples are `AlbumService`, `WorkspaceAlbumService`, `ImportService`, `ModelService`, `StudioService`, `StatusService`, `BackupService`, and `HealthService`. These are not necessarily one-to-one with tables. `ImportService`, for instance, owns preview, duplicate validation, entity reuse/creation, Album and relationship persistence, file movement/copying, repair-state handling after a partial failure, snapshot policy, and the operation record.

Services enforce rules such as:

- Album–Model uniqueness and Album relation validity, including no self-relation.
- Whether a Status, Studio, Model, or related Album can be deleted because it is referenced.
- Canonical path calculation and collision checks.
- Workspace batch-update allow-lists and validation.
- Import preview/execution consistency, database transaction scope, and filesystem repair handling.
- Audit/snapshot policy for material write operations.

Services never execute SQL or inspect `sqlite3` objects. They request persistence through repositories and group database changes through a unit-of-work/transaction abstraction supplied by the database layer.

### API Versioning and Device Access

All external Backend routes use the `/api/v1` prefix. This is the stable API boundary for the Web UI, the Windows AI Worker, CLI tools, and any future out-of-process client. REST is the only supported write entry point for those clients.

Curator does not introduce username/password accounts. It uses device access tokens suitable for explicitly controlled LAN devices. External API calls authenticate with `Authorization: Bearer <token>`. Tokens are stored in the Backend only as hashes; plaintext is shown once at creation and is then stored by the client in protected local configuration.

The `auth_token` table stores token hashes only, never plaintext tokens. Each token has a stable token UUID, token hash, device name, permission scope, creation, expiration and last-used times, and revocation state. Tokens normally have a one-year validity period and support manual revocation and reissuance. Scopes are deliberately small:

- `admin` manages tokens, migrations, restores, backups, and other high-risk administration.
- `writer` performs authorized data writes but cannot perform administrative operations.
- `reader` performs read-only queries.

The AI Worker normally receives only a `writer` token. New tokens are issued only through a local administrator command or a management endpoint bound to loopback; LAN clients cannot self-register or issue tokens. The Backend binds to `127.0.0.1` by default. A LAN bind address is an explicit configuration choice for the Windows AI Worker and should be paired with firewall rules limited to that host.

### Repository Layer

Repositories are the only application abstraction allowed to access persisted Curator records. They express the queries and mutations the Backend needs in domain terms, translate rows to records, and hide SQL, joins, engine-specific syntax, and result conventions.

#### Repository contracts and implementations

The Repository layer has a lightweight separation between a contract and its implementation:

- A **repository contract** describes the persistence operations a Service needs, in application terms.
- The **SQLite implementation** fulfils that contract using the current SQLite schema and SQLite-specific mechanics.
- A future **PostgreSQL implementation** fulfils the same needed contract using PostgreSQL mechanics.

Services depend on repository contracts, not on SQLite or PostgreSQL implementations. This does not require a large abstraction framework or an interface for every small helper. Introduce a contract only where a Service needs a stable persistence boundary or where more than one database implementation will genuinely need to satisfy it.

Repositories should be concrete and focused. A repository can expose purpose-specific methods such as `find_by_id`, `search`, `save`, `delete`, `exists_by_path`, or `replace_models_for_album`; it should not become an unrestricted query executor passed to services or clients.

Read models are Repository result structures prepared for display or API consumption. They are not a requirement to adopt CQRS or a particular Web UI framework. When a real query needs joins, aggregation, filtering, pagination, or statistics, a Repository may return a dedicated read model directly; simple lookup data such as a Status dropdown does not need one.

Examples include an Album list combining Album, Studio, Status, Model count, and Photo count; an Album detail combining the Album, Models, related Albums, and Photos; a Workspace list combining Workspace Album, linked permanent Album, and import state; and an Operations view of recent, failed, and pending-repair operations. Do not design all read models in advance—add them only when an actual UI or API query needs them.

### Database Layer

The database layer owns connection creation, connection configuration, transactions, migrations, and the selection of the active persistence implementation. SQLite connection details, including WAL and foreign-key PRAGMAs, stay here.

It provides repositories with a scoped session/unit of work and commits or rolls back the service-defined transaction. Services should be able to express “perform these changes atomically” without knowing whether the database engine uses SQLite or PostgreSQL.

This is also the correct home for schema migration execution and database health checks. Snapshot backup and restore have SQLite-specific mechanics; they should sit in a SQLite infrastructure adapter called by `BackupService`, rather than being assumed to be a universal database transaction feature.

### Configuration Layer

Configuration is loaded once at startup into a typed, validated application settings object. It owns defaults and validation for paths, port/bind address, database implementation and location, archive/source roots, default Studio, backup retention, log locations, and future PostgreSQL connection settings.

No request should reload configuration or read a global config dictionary. The composition root creates settings, the database provider, infrastructure adapters, repositories, services, and controllers. Tests can construct the same graph with temporary paths and a test database.

### Operation History, Audit, and Snapshots

Curator uses a lightweight **database-first, JSONL-secondary** audit strategy. Important business and operational actions have a small persistent `operation` table/concept so that reliable history and recovery context belong to the database owned by the Backend. JSONL remains a human-readable operational log for diagnosis, but is never the only source of truth.

An operation records a stable operation UUID, type, initiator (Web UI, AI Worker, or CLI), start and end timestamps, status, related entity UUIDs, summary, error details, repair state, and the recovery context needed for the operation. It records actions that occurred; it is not an authorization table and does not replace device access tokens.

Snapshots are reserved for data migrations, bulk writes, restores, and other high-impact or hard-to-reverse operations. Ordinary single writes normally create an audit record according to policy but do not create a snapshot. The Service layer decides this policy; the database-specific snapshot mechanism remains infrastructure.

### Filesystem Consistency and Repair

Filesystem operations cannot share a single atomic transaction with database persistence. If persistence succeeds but a copy, move, or rename fails, the Backend does not automatically delete the database data. Instead, it records the operation as `needs_repair`, including the expected canonical path, completed stages, failure reason, and available repair choices.

Repair is user-selectable and safe. Depending on the verified state, the Backend can offer to retry the original copy or move; safely rename the real folder to the canonical database path; move a conflicting directory to quarantine before retrying; update the database path to a verified real folder after explicit confirmation; or allow manual repair followed by consistency validation. It must never silently overwrite or delete user data.

The canonical path stored in the database is the intended source of truth. When a real directory differs because of trailing spaces or a comparable naming defect, repair should prefer safely renaming the real directory. After repair, the Backend validates agreement between database and filesystem, at minimum covering canonical paths, directory existence, case conflicts, trailing whitespace, and Unicode-normalization conflicts. File manifests, sizes, and hashes may be added later if a concrete validation need justifies them.

One Service-layer path-normalization policy applies to all path creation, import, comparison, and repair. It trims leading and trailing whitespace from every component, normalizes Unicode, detects case-insensitive collisions, and computes an explicit comparison key. If later imports collide after normalization, Services choose deterministic, readable suffixes such as `Name (2)` and `Name (3)`.

### Identity and Constraint Responsibilities

The database enforces hard integrity constraints: UUID uniqueness, foreign keys, required values, join-table uniqueness, and other invariants that must never be violated. Except for small stable lookup tables such as `status`, which may retain integer IDs, business entities use UUIDs as their unique and externally stable identity. APIs, Services, and future clients must not depend on integer IDs for general business entities.

Services own business semantics: path normalization, case-equivalence rules, collision naming, human-readable errors, and repair guidance. Services compute path uniqueness, while the database persists a `canonical_path_key` with a unique constraint as the final safety net against concurrent writes from the Web UI and AI Worker. Database constraints do not replace Service rules; they prevent race conditions from bypassing them.

## 6. Request Flow

For a normal read or write, responsibility flows in one direction:

```text
Web UI / AI Worker / CLI
        -> `/api/v1` HTTP adapter
        -> Domain Service
        -> Repository
        -> Database
```

For an Album update, the Controller parses the route ID and request DTO, then calls `AlbumService.update_album`. The service validates the complete Album change and relationship rules, begins one unit of work, asks repositories to update the Album and replace its permitted relationship sets, commits on success, records the operation where policy requires it, and returns a result. The Controller maps that result to the HTTP response.

For an import, the flow includes two controlled infrastructure collaborators:

```text
Client -> `/api/v1` adapter -> ImportService
                               -> repositories -> database transaction
                               -> filesystem adapter
                               -> audit / backup adapters
```

The Service explicitly owns the order, result reporting, snapshot decision, and repair-state policy because a database and filesystem cannot share one atomic transaction. The Controller must not decide this sequence.

## 7. Repository Pattern

Repository is the only database access abstraction above the database layer. This makes persistence visible, testable, and replaceable while keeping Curator's real queries close to the entities they concern.

Suggested initial repository contracts include:

| Repository | Responsibilities |
| --- | --- |
| `AlbumRepository` | Find/search Albums; retrieve Album detail; create/update/delete Albums; persist Album–Model, Album relation, and Photo changes needed by Album workflows; check canonical path and album duplicate conditions. |
| `WorkspaceAlbumRepository` | List/search/get Workspace Albums; obtain workspace options; apply validated single and batch updates; resolve workspace-to-permanent Album references and Workspace `belongs_to` references. |
| `ModelRepository` | Find/search/get Models; create/update/delete Models; find an existing Model by supported name matching; list Albums for a Model. |
| `StudioRepository` | Find/search/get Studios; create/update/delete Studios; find by name; list Albums for a Studio. |
| `StatusRepository` | List/get/create/update/delete Statuses and report reference counts required for deletion rules. |
| `OperationRepository` or audit adapter | Persist and query the database-first operation history, including failed and `needs_repair` operations; emit JSONL as supporting diagnostic output. |

`AlbumRepository` may internally use SQL across `album`, `album_model`, `album_relation`, and `photo`. The repository boundary is about application ownership, not an artificial insistence on one table per class.

Services must never execute SQL directly because otherwise rules become coupled to row shape, SQL dialect, transaction mechanics, and database error behavior. A service should state intent—“replace this Album's Models” or “find a duplicate import target”—and a repository should implement the persistence detail. This also prevents the AI Worker or CLI from becoming an informal second persistence layer.

## 8. Database Abstraction

SQLite is the current database implementation and remains the default. The architecture should not hide useful SQLite behavior prematurely; it should confine it to `database/sqlite` and SQLite repository implementations.

The upper layers depend on repository contracts and a small unit-of-work/transaction contract. They do not depend on:

- `sqlite3.Connection`, `sqlite3.Row`, `lastrowid`, or PRAGMA commands.
- SQLite placeholder, date, upsert, or schema-introspection syntax.
- A filesystem path to `Curator.db`.
- The SQLite backup API.

A later PostgreSQL migration follows this sequence:

1. Add PostgreSQL connection/session and transaction support in the database layer.
2. Implement the same repository contracts with PostgreSQL SQL and row mapping.
3. Map legacy integer-ID relationships completely to UUID foreign keys and produce a one-time old-ID-to-UUID mapping report for validation, troubleshooting, and rollback.
4. Select the implementation through configuration and run migration/data-transfer tooling.
5. Replace SQLite-only snapshot behavior with a PostgreSQL-appropriate backup/restore operational implementation.

Controllers and Services do not change merely because the selected database changes. Some operational behavior will intentionally differ: SQLite file snapshots cannot be treated as the PostgreSQL backup mechanism. That distinction belongs behind `BackupService` and its database-specific adapter.

This is database independence, not database-feature denial. Repository contracts should reflect Curator needs, and only create a cross-engine contract after a concrete second implementation needs it.

## 9. Suggested Project Structure

The final names can follow the existing repository conventions, but the following small structure gives each responsibility a discoverable home:

```text
backend/
  app.py                         # Composition root and server startup
  config.py                      # Settings loading and validation
  api/
    router.py
    controllers/
      albums.py
      models.py
      studios.py
      workspace.py
      imports.py
      operations.py              # backups, rollback, health
  services/
    albums.py
    models.py
    studios.py
    workspace_albums.py
    imports.py
    backups.py
  repositories/
    albums.py                    # Contracts or shared record definitions
    models.py
    studios.py
    workspace_albums.py
    statuses.py
  database/
    unit_of_work.py
    migrations/
    sqlite/
      connection.py
      album_repository.py
      model_repository.py
      studio_repository.py
      workspace_album_repository.py
      status_repository.py
    postgresql/                  # Added only when migration work begins
  infrastructure/
    filesystem.py                # copy/move and destination checks
    audit_log.py
    backups_sqlite.py
    scheduler.py
  contracts/                     # Request/query/result DTOs shared by API and CLI
  tests/
    services/
    repositories/
    api/
```

This does not require moving everything at once. Existing `tools/web_ui/static` assets can remain where they are. During transition, `tools/web_ui/server.py` can become a thin launch point that imports the Backend composition root, preserving the current command and local port behavior. The disabled earlier base app remains historical reference only and is deleted only after the completed, verified migration retires its entry point.

## 10. Migration Strategy

Migration should be incremental, behavior-preserving, and accompanied by focused tests. Do not start by moving every function or replacing the HTTP server.

1. **Establish a safety baseline.** Document the supported routes and current Web UI behavior; add tests around critical existing flows: Album relationship updates, reference-protected deletes, Workspace batch edits, import preview/execution, backup/rollback, audit history, and filesystem repair. The disabled `workspace/curator_base_app` is historical context, not a migration target.
2. **Extract configuration and database connection setup.** Introduce one settings object and one SQLite connection/unit-of-work provider. Keep the current route handlers operational, but replace duplicated global loading and `open_db` mechanics with the new provider.
3. **Extract repositories for reads.** Start with `ModelRepository`, `StudioRepository`, `StatusRepository`, and read-only `AlbumRepository`/`WorkspaceAlbumRepository` queries. Controllers call repositories temporarily only if necessary; then introduce thin query services. This is a low-risk way to verify mapping and pagination boundaries.
4. **Move one simple write use case at a time.** Implement services and repository writes for Model and Studio create/update/delete, including current reference checks. Retain endpoint shapes while handlers become thin Controllers.
5. **Migrate Album workflows as a unit.** Move Album create/update/delete plus Models, relations, and Photos into `AlbumService` and `AlbumRepository`. Keep the existing all-or-nothing transaction semantics, then add targeted tests for relation and reference rules.
6. **Migrate Workspace workflows.** Move Workspace listing, detail, single edits, and batch edits behind `WorkspaceAlbumService` and its repository. Preserve allow-lists, validation, the high-impact snapshot policy, and operation results.
7. **Migrate import deliberately.** Extract `ImportService` with preview first, then execution. Make its database transaction, file-operation sequence, `needs_repair` state, repair options, snapshot policy, and audit record explicit. This is the highest-risk workflow and should not be mechanically moved.
8. **Extract operational services.** Move backup cataloging, retention, restore, database-first operation history with JSONL support, and daily scheduling into operational Services and infrastructure adapters. Preserve local-first binding, controlled LAN access, and recovery behavior.
9. **Consolidate entry points.** Once feature parity is verified, make the new Backend the sole entry point. Delete `workspace/curator_base_app` only after Migration is complete, verified, and its legacy entry point is confirmed retired. Delete either historical `server.py` only after its required behavior has been migrated and tested and the new Backend is the sole entry point.
10. **Prepare PostgreSQL only when justified.** Add contract tests shared by SQLite repositories first. Introduce PostgreSQL adapters and data migration tooling later, without changing services or API behavior unnecessarily.

At every step, maintain a working application, retain database backups before material changes, and prefer small reviewable commits. Do not run both old and new writers against the same behavior indefinitely; cut a migrated operation over to one service once verified.

## 11. Open Questions

The following decisions should be resolved before their corresponding implementation step:

- What exact request and error-response envelope should `/api/v1` use, including validation-error and conflict representations?
- Which specific operations meet the high-impact or hard-to-reverse threshold for snapshots, and what retention schedule applies to each category?
- What repair-state values and confirmation screens are needed to make filesystem repair clear without overwhelming the local Web UI?
- What is the quarantine location, retention policy, and recovery procedure for conflicting directories?
- Which path components are subject to canonical-path uniqueness, and how should existing data be assessed before the unique `canonical_path_key` safety net is introduced?
- Which entity UUIDs must be included in operation records for each workflow, and what summary/error data remains safe and useful to retain?
- What secure local configuration mechanism should each client use to store its one-time-issued device token?
- Which firewall, TLS, and network-binding guidance is appropriate if the Windows AI Worker access moves from a trusted LAN to a less controlled environment?
- Which concrete UI/API queries first justify a dedicated Repository read model?
- What PostgreSQL data-transfer validation, rollback rehearsal, and old-ID-to-UUID mapping-report format are required when migration becomes an active project?

## 12. Architecture, Specification, and Implementation

Curator development follows this documentation hierarchy:

```text
Vision
  ↓
Architecture
  ↓
Specification
  ↓
Implementation
```

Architecture defines enduring responsibilities, boundaries, principles, and the reasons for them. Specifications follow the Architecture: they define the module contracts, rules, and implementation requirements needed for a bounded change. Implementation follows approved Specifications and contains executable code only.

A lower layer must not redefine a concept or decision made by a higher layer. Implementation must not invent new architecture. If implementation exposes the need for a new architectural decision, update this Architecture document or add the appropriate ADR before implementation proceeds.
