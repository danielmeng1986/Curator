# Curator Backend Architecture

## Purpose and scope

This document designs the next generation of the Curator Backend before implementation begins. It is an incremental refactoring target for the existing local Python backend, not a proposal to replace Curator's domain model, UI, SQLite database, or local-first deployment model.

Curator Backend owns the database. Angular, the AI Worker, the CLI, and any future client communicate with the Backend; they never open `Curator.db` or issue SQL themselves. The Backend owns validation, business rules, transaction boundaries, persistence, audit logging, and recovery-oriented operations.

The design deliberately favors a small number of explicit modules over frameworks, dependency-injection containers, generic CRUD engines, or a separate service for every entity. Curator is maintained by one developer, so each abstraction must address a current source of coupling.

## 1. Architecture Principles

These principles are the foundation for all Curator Backend work. They apply to future Specifications and Implementation work unless an Architecture Decision Record explicitly changes them.

- **Backend owns the database.** The Backend is the single owner of database access, writes, transactions, persistence rules, and schema evolution.
- **Clients never access the database directly.** Angular, the AI Worker, the CLI, and local tools request Backend operations; they do not open `Curator.db`, run SQL, or bypass validation.
- **Repository hides persistence.** Repositories are the persistence boundary. They hide database-specific queries, rows, and engine behavior from the application layer.
- **Services own business rules.** Validation, workflow decisions, transaction boundaries, and multi-resource coordination belong to Services, independent of the client that initiated the work.
- **Controllers translate HTTP.** HTTP Controllers are adapters: they translate requests to application operations and results to HTTP responses. They do not contain SQL or business workflows.
- **Repositories translate persistence.** A repository translates application persistence needs to the selected database implementation and translates persisted results back to application records.
- **Business logic must never depend on SQL.** Services express Curator intent and rules, not tables, SQL syntax, or SQLite connection behavior.
- **Incremental evolution over large rewrites.** Improve one bounded workflow at a time while preserving working behavior and recovery options.
- **Local-first architecture.** Curator remains a local application by default. Future clients use Backend boundaries without changing this ownership model.
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

Both modules use Python's standard-library HTTP server and SQLite directly. The newer server is the practical reference for the current full UI; the earlier server contains related workflows and operational behavior that should be preserved or consciously consolidated during migration.

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

- Adding Angular, an AI Worker, or a CLI would either duplicate business rules in each client or add more routes to an already broad handler.
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
4. **Multiple clients.** The same Backend use cases support Angular, the AI Worker, and the CLI. Clients use an API or a deliberately supported in-process command entry point; neither client type accesses the database directly.
5. **PostgreSQL readiness.** SQLite remains the current implementation. A later PostgreSQL implementation replaces the database/repository wiring, not controllers or business rules.
6. **Preserve the current model and workflow.** `model`, `studio`, `album`, `photo`, `album_model`, `album_relation`, `status`, and `workspace_album` retain their current concepts and relationships. This architecture does not redesign them.
7. **Safe incremental delivery.** Move one use case at a time behind a tested boundary, retaining existing routes and behavior until replacements are verified.
8. **Appropriate simplicity.** Prefer concrete repositories and small services. Do not introduce microservices, an ORM solely for abstraction, event buses, CQRS infrastructure, or a framework migration unless a real later need justifies it.

## 5. Proposed Backend Architecture

The Backend is a modular monolith: one local process, one API, one database owner, and clear internal layers. Dependencies point inward:

```text
Clients (Angular / AI Worker / CLI)
        -> Controller / API
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

Controllers should be organised by API capability rather than one class per SQL table: for example `albums`, `models`, `studios`, `workspace`, `imports`, `operations`, and `health`. A Controller may combine service results into an API response, but it must not recreate service rules.

HTTP is only one way to enter the application. REST is the shared external adapter for Angular and an out-of-process AI Worker. A CLI may use the REST API, while a local command runner may invoke the same Service operation directly through a supported application entry point. These are adapters with different input/output formats, not separate homes for business logic. Every adapter reaches Services; no adapter reaches repositories or SQLite directly.

### Domain Service Layer

Services implement Curator use cases and own their business rules. They receive validated command/query objects, coordinate repositories and infrastructure, select transaction boundaries, and return application results independent of HTTP.

Examples are `AlbumService`, `WorkspaceAlbumService`, `ImportService`, `ModelService`, `StudioService`, `StatusService`, `BackupService`, and `HealthService`. These are not necessarily one-to-one with tables. `ImportService`, for instance, owns preview, duplicate validation, entity reuse/creation, Album and relationship persistence, file movement/copying, compensation after a partial failure, snapshot creation, and the operation record.

Services enforce rules such as:

- Album–Model uniqueness and Album relation validity, including no self-relation.
- Whether a Status, Studio, Model, or related Album can be deleted because it is referenced.
- Canonical path calculation and collision checks.
- Workspace batch-update allow-lists and validation.
- Import preview/execution consistency, database transaction scope, and filesystem compensation.
- Audit/snapshot policy for material write operations.

Services never execute SQL or inspect `sqlite3` objects. They request persistence through repositories and group database changes through a unit-of-work/transaction abstraction supplied by the database layer.

### Repository Layer

Repositories are the only application abstraction allowed to access persisted Curator records. They express the queries and mutations the Backend needs in domain terms, translate rows to records, and hide SQL, joins, engine-specific syntax, and result conventions.

#### Repository contracts and implementations

The Repository layer has a lightweight separation between a contract and its implementation:

- A **repository contract** describes the persistence operations a Service needs, in application terms.
- The **SQLite implementation** fulfils that contract using the current SQLite schema and SQLite-specific mechanics.
- A future **PostgreSQL implementation** fulfils the same needed contract using PostgreSQL mechanics.

Services depend on repository contracts, not on SQLite or PostgreSQL implementations. This does not require a large abstraction framework or an interface for every small helper. Introduce a contract only where a Service needs a stable persistence boundary or where more than one database implementation will genuinely need to satisfy it.

Repositories should be concrete and focused. A repository can expose purpose-specific methods such as `find_by_id`, `search`, `save`, `delete`, `exists_by_path`, or `replace_models_for_album`; it should not become an unrestricted query executor passed to services or clients.

Read models that need joins or counts remain repository responsibilities. It is reasonable for `AlbumRepository` to return an Album detail record containing its Models, relations, and Photos, or a paginated Album list item with Studio/Status/model display data. That preserves a useful API without forcing service code to assemble SQL-shaped results.

### Database Layer

The database layer owns connection creation, connection configuration, transactions, migrations, and the selection of the active persistence implementation. SQLite connection details, including WAL and foreign-key PRAGMAs, stay here.

It provides repositories with a scoped session/unit of work and commits or rolls back the service-defined transaction. Services should be able to express “perform these changes atomically” without knowing whether the database engine uses SQLite or PostgreSQL.

This is also the correct home for schema migration execution and database health checks. Snapshot backup and restore have SQLite-specific mechanics; they should sit in a SQLite infrastructure adapter called by `BackupService`, rather than being assumed to be a universal database transaction feature.

### Configuration Layer

Configuration is loaded once at startup into a typed, validated application settings object. It owns defaults and validation for paths, port/bind address, database implementation and location, archive/source roots, default Studio, backup retention, log locations, and future PostgreSQL connection settings.

No request should reload configuration or read a global config dictionary. The composition root creates settings, the database provider, infrastructure adapters, repositories, services, and controllers. Tests can construct the same graph with temporary paths and a test database.

## 6. Request Flow

For a normal read or write, responsibility flows in one direction:

```text
Angular / AI Worker / CLI
        -> HTTP Controller
        -> Domain Service
        -> Repository
        -> Database
```

For an Album update, the Controller parses the route ID and request DTO, then calls `AlbumService.update_album`. The service validates the complete Album change and relationship rules, begins one unit of work, asks repositories to update the Album and replace its permitted relationship sets, commits on success, records the operation where policy requires it, and returns a result. The Controller maps that result to the HTTP response.

For an import, the flow includes two controlled infrastructure collaborators:

```text
Client -> ImportController -> ImportService
                               -> repositories -> database transaction
                               -> filesystem adapter
                               -> audit / backup adapters
```

The service explicitly owns the order, result reporting, and compensation policy because a database and filesystem cannot share one atomic transaction. The Controller must not decide this sequence.

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
| `OperationRepository` or audit adapter | Persist/query structured operation records when JSONL logging evolves into an owned persistence concern. Keep this small; do not force a new database table before it is needed. |

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
3. Select the implementation through configuration and run migration/data-transfer tooling.
4. Replace SQLite-only snapshot behavior with a PostgreSQL-appropriate backup/restore operational implementation.

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

This does not require moving everything at once. Existing `tools/web_ui/static` assets can remain where they are. During transition, `tools/web_ui/server.py` can become a thin launch point that imports the Backend composition root, preserving the current command and local port behavior. The earlier base app can either call the same API or be retired only after its distinct workflows have been migrated.

## 10. Migration Strategy

Migration should be incremental, behavior-preserving, and accompanied by focused tests. Do not start by moving every function or replacing the HTTP server.

1. **Establish a safety baseline.** Document the supported routes and current behavior; add tests around critical existing flows: Album relationship updates, reference-protected deletes, Workspace batch edits, import preview/execution, and backup/rollback. Record any intentional differences between the two existing servers.
2. **Extract configuration and database connection setup.** Introduce one settings object and one SQLite connection/unit-of-work provider. Keep the current route handlers operational, but replace duplicated global loading and `open_db` mechanics with the new provider.
3. **Extract repositories for reads.** Start with `ModelRepository`, `StudioRepository`, `StatusRepository`, and read-only `AlbumRepository`/`WorkspaceAlbumRepository` queries. Controllers call repositories temporarily only if necessary; then introduce thin query services. This is a low-risk way to verify mapping and pagination boundaries.
4. **Move one simple write use case at a time.** Implement services and repository writes for Model and Studio create/update/delete, including current reference checks. Retain endpoint shapes while handlers become thin Controllers.
5. **Migrate Album workflows as a unit.** Move Album create/update/delete plus Models, relations, and Photos into `AlbumService` and `AlbumRepository`. Keep the existing all-or-nothing transaction semantics, then add targeted tests for relation and reference rules.
6. **Migrate Workspace workflows.** Move Workspace listing, detail, single edits, and batch edits behind `WorkspaceAlbumService` and its repository. Preserve allow-lists, validation, snapshots, and operation results.
7. **Migrate import deliberately.** Extract `ImportService` with preview first, then execution. Make its database transaction, file-operation sequence, compensation path, snapshot, and audit record explicit. This is the highest-risk workflow and should not be mechanically moved.
8. **Extract operational services.** Move backup cataloging, retention, restore, audit logging, and daily scheduling into `BackupService` and infrastructure adapters. Preserve local-only binding and recovery behavior.
9. **Consolidate entry points.** Once feature parity is verified, make the newer Web UI and any retained legacy pages use one Backend API/composition root. Remove duplicated backend behavior only after a replacement has tests and an approved migration note.
10. **Prepare PostgreSQL only when justified.** Add contract tests shared by SQLite repositories first. Introduce PostgreSQL adapters and data migration tooling later, without changing services or API behavior unnecessarily.

At every step, maintain a working application, retain database backups before material changes, and prefer small reviewable commits. Do not run both old and new writers against the same behavior indefinitely; cut a migrated operation over to one service once verified.

## 11. Open Questions

The following decisions should be resolved before their corresponding implementation step:

- Which current server is the canonical production entry point during the transition, and which legacy routes/workflows must be preserved from `workspace/curator_base_app`?
- What stable API versioning and error-response convention should all clients receive? A simple `/api/v1` prefix may be sufficient once external clients depend on it.
- Should the AI Worker always call the local HTTP API, or is there a supported in-process command runner for local batch work? In either case, it must not access the database directly.
- Which operations require a pre-operation snapshot, and which only require an audit entry? Define a clear policy rather than duplicating snapshot decisions in endpoints.
- Where should operation/audit records live long term: continue JSONL with a defined schema, add a small database-backed operation history later, or support both during migration?
- What exact import failure policy is acceptable when database persistence succeeds but a filesystem move/copy fails: compensating delete, a recoverable pending state, or a recorded manual-recovery state? This must be explicit for permanent Album import and Workspace import.
- What constraints should be database-enforced now versus service-enforced (unique paths, duplicate Studio/title rule, relationship uniqueness, and case-insensitive identity matching)?
- Does PostgreSQL migration need to preserve integer IDs as well as UUIDs, and what data/export/rollback plan will make the cutover safe?
- What authentication or local-process trust model will be needed if the AI Worker becomes a separate process or the Backend eventually binds beyond loopback?
- Which query/reporting needs deserve dedicated repository read models before Angular replaces the current static UI?

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
