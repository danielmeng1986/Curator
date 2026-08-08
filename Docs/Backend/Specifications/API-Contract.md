# Curator Backend API Contract

## Purpose and scope

This document defines the shared, stable API contract for Curator Backend. It applies to the Web UI, Windows AI Worker, CLI tools, and every future out-of-process client using `/api/v1`.

It defines cross-cutting response, error, metadata, access, and collection rules. It does not define a route catalogue, resource-specific payloads, database representation, or HTTP-library behavior. Route-specific specifications MAY add fields and rules needed by their workflows, but they MUST NOT violate this contract.

## Relationship to existing documentation

[Backend Architecture](../Backend-Architecture.md) defines responsibilities and layer boundaries. [API Specification](API-Specification.md) defines the external HTTP boundary and request flow. This contract defines the shared shape of responses, errors, metadata, and access rules used at that boundary.

The Architecture and this contract govern every route-specific specification. If a route-specific specification conflicts with this contract, this contract wins unless a formal ADR updates the Architecture and this contract is then revised to reflect that decision.

## Authentication and transport rules

All normal `/api/v1` routes MUST require `Authorization: Bearer <token>`. Tokens, approval, and scopes are defined by [Authentication](Authentication.md). The Windows AI Worker uses HTTP REST with bearer-token authentication.

The only possible exceptions are explicitly declared local-only routes, unauthenticated health/status routes, loopback-only diagnostics, and an explicit public/bootstrap route. Binding the Backend to loopback does not itself remove an authentication requirement. No route is unauthenticated by implication.

Clients MUST use the API boundary. They MUST NOT access Repositories, Services, the database, or other Backend internals directly. API adapters authenticate, authorize, and validate transport shape before invoking a Service; Services determine business outcomes; adapters translate those outcomes without inventing business state, snapshots, or repair decisions.

## Standard response envelope

Every response with a body MUST use one of the following envelopes. Normal successful responses, including `201 Created` and `202 Accepted`, use the success envelope. Successful operations do not use an alternate `204 No Content` representation.

```json
{
  "data": {},
  "meta": {
    "request_id": "..."
  }
}
```

```json
{
  "error": {
    "code": "...",
    "message": "...",
    "details": {},
    "fields": {}
  },
  "meta": {
    "request_id": "..."
  }
}
```

`data` contains the route result and MAY be an object, array, scalar, or `null` when the route-specific contract permits it. `meta` is always present. `meta.request_id` is a Backend-generated correlation identifier and MUST be present in both envelopes.

`error.details` and `error.fields` are optional. A route MUST omit an optional field rather than supply a meaning-changing alternative shape. `error.fields`, when present, maps a client-visible field name to one or more stable error descriptors for that field.

The following optional `meta` members have one project-wide meaning:

| Member | Meaning |
| --- | --- |
| `pagination` | The canonical collection page metadata defined below. |
| `filters` | The normalized filters applied to a collection query. |
| `sort` | The normalized sort keys applied to a collection query. |
| `operation` | An object containing the material operation's stable `id`; it MAY include a route-defined status or linkable summary. |
| `snapshot` | An object containing the related snapshot's stable `id`, when a snapshot exists. |
| `confirmation` | An object describing an action awaiting explicit client confirmation. |
| `repair` | An object describing an unresolved repair state and its available route-defined next actions. |

Operation, snapshot, confirmation, and repair information belongs in `meta`, never in competing top-level fields. This keeps a route's `data` focused on its resource or result while preserving a consistent workflow vocabulary.

## Status code mapping

The API uses the following canonical mapping. The status code expresses the response class; the stable error `code` expresses the client-actionable condition.

| Condition | Status | Required error code family and behavior |
| --- | --- | --- |
| Malformed JSON, missing required transport field, invalid query type, or invalid pagination syntax | `400 Bad Request` | `REQUEST_*`; rejected before Service invocation. |
| Domain or business validation failure | `422 Unprocessable Content` | `VALIDATION_*`; the request was syntactically usable, but its requested meaning is invalid. |
| Missing, invalid, expired, malformed, or revoked token | `401 Unauthorized` | `AUTHENTICATION_*`; do not invoke the protected Service operation. |
| Valid token lacks required scope | `403 Forbidden` | `AUTHORIZATION_*`; do not perform the operation. |
| Required resource does not exist or is not visible to the token | `404 Not Found` | `NOT_FOUND`; do not disclose protected resource details. |
| Data or business conflict | `409 Conflict` | `DATA_CONFLICT` or `BUSINESS_CONFLICT`; do not claim completion. |
| Explicit confirmation is required before the action may proceed | `428 Precondition Required` | `CONFIRMATION_REQUIRED`; include `meta.confirmation`. |
| An operation is unresolved and requires repair | `409 Conflict` | `NEEDS_REPAIR`; include `meta.operation` and `meta.repair`. |
| Unexpected Backend failure | `500 Internal Server Error` | `INTERNAL_ERROR`; do not expose implementation details. |

`422` is the project standard for domain validation because it separates a well-formed request whose business meaning is invalid from a malformed transport request (`400`). `428` is a distinct confirmation-required outcome because confirmation is an explicit precondition, not a data conflict. It MUST include the confirmation state needed for the client to present or submit that decision.

`409` is reserved for an otherwise understandable request that cannot be completed against current state. `DATA_CONFLICT` covers concurrent uniqueness, version, integrity, or equivalent competing-state conflicts. `BUSINESS_CONFLICT` covers a valid request blocked by a current workflow or lifecycle state. `NEEDS_REPAIR` also uses `409`, but is distinct: it reports an existing incomplete operation that requires repair and is never a completed success.

## Error model

Every error object MUST contain a stable machine-readable `code` and a safe, user-presentable `message`. `details` MAY provide structured context, such as an expected state, supported values, or a retry-safe action. It MUST NOT expose SQL, filesystem internals, stack traces, framework names, token material, or other implementation-sensitive data.

`fields` MAY appear only for request or domain validation errors. Its keys MUST use the same field names clients submit or receive. Clients and automation MUST branch on `error.code`, HTTP status, and documented structured fields—not on message text.

The error model distinguishes the following classes:

| Class | Owner and representation |
| --- | --- |
| Transport validation | API adapter; `400` and `REQUEST_*`. |
| Business validation | Service; `422` and `VALIDATION_*`, optionally with `fields`. |
| Authentication and authorization | API adapter; `401`/`403` and `AUTHENTICATION_*`/`AUTHORIZATION_*`. |
| Conflict | Service outcome exposed by adapter; `409` and `DATA_CONFLICT` or `BUSINESS_CONFLICT`. |
| Repair-required workflow state | Service outcome exposed by adapter; `409`, `NEEDS_REPAIR`, `meta.operation`, and `meta.repair`. |

Where material work has started, `meta.operation.id` MUST be included whenever the applicable workflow requires an Operation record. `meta.request_id` remains available for correlation even where no Operation exists.

## Pagination and list metadata

All list endpoints MUST use cursor pagination. Clients send an opaque `cursor` and a positive integer `limit`; the first page omits `cursor`. A cursor is a continuation token, not an offset, database key, or encoded table representation. Clients MUST treat it as opaque and MUST NOT construct, inspect, or reuse it with a materially different query.

Cursor pagination is the standard because it remains stable as collections grow and avoids coupling clients to row offsets or persistence ordering. It requires a stable, documented effective sort for each route; a route MAY define a default sort, but MUST report it in `meta.sort`.

Every list response MUST put its collection in `data` and include this complete metadata shape:

```json
{
  "meta": {
    "request_id": "...",
    "pagination": {
      "cursor": null,
      "limit": 50,
      "next_cursor": "...",
      "has_more": true,
      "total": null
    },
    "filters": [],
    "sort": []
  }
}
```

`cursor` is `null` for the first page; `next_cursor` is `null` when no further page is available. `total` is an integer when the route can provide it without changing the route's documented query semantics; otherwise it is `null`. `has_more` is always boolean. `filters` and `sort` are always present, including when empty.

List endpoints returning read models MUST use this same metadata shape. Response data and metadata describe API-facing results only; clients MUST NOT infer database tables, joins, or storage behavior from either.

## Filtering and sorting conventions

List routes MAY expose resource-specific filters, but MUST use these query forms and report their normalized application in `meta.filters` and `meta.sort`.

| Need | Query form | Example |
| --- | --- | --- |
| Exact match | `filter[field]=value` | `filter[status]=active` |
| Partial/text match | `filter[field][contains]=value` | `filter[title][contains]=summer` |
| General route-defined text search | `q=value` | `q=beach` |
| Sort | `sort=field,-other_field` | `sort=title,-created_at` |

An unprefixed sort key is ascending; `-` is descending. When multiple sort keys are supported, they are applied left to right; routes MUST add a deterministic tie-breaker where required for cursor continuity and report the effective order. The normalized metadata form is an ordered array of objects: `{"field":"title","operator":"contains","value":"summer"}` for filters and `{"field":"created_at","direction":"desc"}` for sort keys.

Unsupported filters, operators, sort fields, duplicate incompatible filters, or invalid values MUST be rejected as transport-query errors with `400` and a `REQUEST_*` code. A route MUST NOT silently ignore them. Resource-specific filters MAY extend the available field set, not this syntax or metadata convention.

## Read models

A read model is a stable API-facing display or query result designed for a client journey. It is not a promise about a database table, entity, join, persistence record, or internal query strategy. It MAY be produced by a Repository query, joins, aggregation, or another internal mechanism.

For example, an album-list read model may expose album display information, Studio and Status labels, and aggregate counts; a normalize-workspace read model may expose candidate normalization state and review flags; an import-preview read model may expose proposed changes, collisions, and eligibility. Different user journeys MAY use different read models for the same underlying business concepts.

Clients MUST treat read models as API shapes only. They MUST NOT infer or depend on underlying tables, columns, relations, query mechanics, or persistence ownership.

## Local-only and unauthenticated routes

The Backend recognizes only these policy categories:

1. **Health/status endpoints** MAY be unauthenticated when explicitly declared and limited to safe availability information.
2. **Loopback-only diagnostics** MAY be unauthenticated only when explicitly declared, bound to loopback, and limited to safe diagnostics.
3. **Public/bootstrap routes** MAY exist only when explicitly declared by a route specification and must state their purpose, exposure, allowed inputs, and rate/abuse safeguards.

Every exception MUST be declared by its route-specific specification, including whether it is local-only and whether authentication is waived. Until a route is so declared, it is a normal bearer-token-protected route.

The Authentication Specification declares exactly these current loopback-only
exceptions outside `/api/v1`:

| Route | Unauthenticated purpose and constraint |
| --- | --- |
| `POST /api/auth/registrations` | Submit a registration bearing the configured registration proof; it creates Pending Approval only and never issues a Token. |
| `GET /api/auth/bootstrap/status` | Disclose only whether first Admin initialization is complete and whether a current Code is available. |
| `POST /api/auth/bootstrap/complete` | Consume a console-created, short-lived, single-use Code to establish the first Admin exactly once. |

All three reject non-loopback clients. Registration approval and every later
authentication-management action use bearer-protected `/api/v1` routes with
Admin scope. In particular, there is no unauthenticated loopback approval route.

## Confirmation-required and repair-required outcomes

An action is confirmation-required when a Service has determined that an otherwise eligible action needs a deliberate client decision before irreversible, high-risk, destructive, or user-choice-dependent work may begin. The unconfirmed request MUST NOT perform the confirmation-gated action.

A `428` response MUST contain `error.code: "CONFIRMATION_REQUIRED"` and `meta.confirmation`. That object MUST contain a route-defined confirmation `id`, a `required` value of `true`, and enough safe summary context for the client to present the decision. The route specification MUST define the subsequent request's confirmation field or token. A confirmed request MUST supply that field or token exactly as specified; it is a new request that permits the Service to proceed, not a client-side reinterpretation of the prior response.

A repair-required outcome occurs when work has not reached a completed, consistent state and the Service requires repair or verification. It MUST return `409` with `error.code: "NEEDS_REPAIR"`, `meta.operation.id`, and `meta.repair`. `meta.repair` MUST include the current repair `state` and MAY include safe available actions and verification context. It is not a successful completion response.

The API adapter relays the Service outcome. It MUST NOT create its own snapshot reference, decide that repair is resolved, or manufacture a confirmation requirement. Operation identifiers identify auditable material work; snapshot references identify snapshots selected by the Service under the Snapshot Specification. Repair state follows the Repair Workflow.

## Illustrative examples

These examples show shared shapes only. They do not commit any particular route or resource to the example fields.

### Successful list response

```json
{
  "data": [
    {"id":"album-01","title":"Summer archive","studio":"Northlight","photo_count":42}
  ],
  "meta": {
    "request_id":"req-01",
    "pagination":{"cursor":null,"limit":50,"next_cursor":"opaque-next-token","has_more":true,"total":null},
    "filters":[{"field":"status","operator":"exact","value":"active"}],
    "sort":[{"field":"title","direction":"asc"},{"field":"id","direction":"asc"}]
  }
}
```

### Validation error

```json
{
  "error": {
    "code":"VALIDATION_INVALID_TITLE",
    "message":"The title does not meet the required naming rules.",
    "fields":{"title":[{"code":"INVALID_FORMAT","message":"Use a non-empty title."}]}
  },
  "meta":{"request_id":"req-02"}
}
```

### Conflict response

```json
{
  "error": {
    "code":"DATA_CONFLICT",
    "message":"The requested change conflicts with current state.",
    "details":{"resource_id":"album-01"}
  },
  "meta":{"request_id":"req-03","operation":{"id":"op-01"}}
}
```

### Confirmation-required response

```json
{
  "error":{"code":"CONFIRMATION_REQUIRED","message":"This action requires explicit confirmation before it can proceed."},
  "meta":{
    "request_id":"req-04",
    "confirmation":{"id":"confirm-01","required":true,"summary":"The action will apply the reviewed changes."}
  }
}
```

### Needs-repair response

```json
{
  "error":{"code":"NEEDS_REPAIR","message":"The operation is incomplete and requires repair before it can be treated as complete."},
  "meta":{
    "request_id":"req-05",
    "operation":{"id":"op-02"},
    "repair":{"state":"NeedsRepair","available_actions":["retry","review"]}
  }
}
```
