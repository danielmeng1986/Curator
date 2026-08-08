# BT-032 — Complete Album Management API Readiness

## Task ID

`BT-032` — Status: `Complete`

## Title

Complete Album Query, Batch Mutation, and Relationship Validation Contracts

## Related Specification(s)

- [API Specification](../Specifications/API-Specification.md), Album collection and mutation contracts.
- [Operation Logging](../Specifications/Operation-Logging.md), durable material-write evidence.
- [UI Data Interaction Rules](../../UI/02_Data_Interaction_Rules.md), Album filters and relationship rules.
- [UI Entity Management](../../UI/03_Entity_Management.md), Album management surface.

## Goal

Provide the authenticated Backend contracts required for `UI-005` to manage Albums as the primary permanent-asset unit without implementing business rules in the browser.

## Scope

- Extend Album search across title, Studio, location, scene, and linked Model labels.
- Add capture-date and publish-date range filters and preserve supported sorting and pagination combinations.
- Add deterministic Album batch-change preview and execution contracts with reviewed-preview identity/version checks.
- Prevent silent replacement of non-empty values unless the reviewed request explicitly permits it.
- Validate Album–Model and `BELONGS_TO` Album relationships for existence, self-reference, and duplicates.
- Translate invalid fields to structured `400` responses and conflicts/stale previews to structured `409` responses.
- Return per-item and aggregate batch results and durable Operation links.

## Out of Scope

- Photo browsing or independent Photo CRUD in `apps.web`.
- Album or Photo filesystem deletion, Trash, Quarantine, or permanent purge.
- AI Collection Workspace review models.

## Dependencies

- `BT-003`, `BT-005`, `BT-012`, and `BT-013` — API envelopes, repository boundaries, Operation evidence, and authenticated scopes.
- The accepted Album-as-management-unit decisions recorded by `UI-005`.

## Implementation Steps

1. Normalize the Album collection query parameters and document their combinations in the API Specification.
2. Add batch preview identity, stale-input detection, explicit overwrite policy, execution, and result read models.
3. Centralize Album relationship validation in the service boundary and map persistence conflicts to stable API errors.
4. Add focused repository, service, API, authorization, zero-write-preview, and stale/replay tests.

## Acceptance Criteria

- Search and each date range return the same ordered, paginated collection through repository and `/api/v1` tests.
- Batch preview performs no business mutation; execution rejects changed/stale preview identity with no partial write.
- A batch request never overwrites a non-empty field unless that consequence was explicitly reviewed.
- Missing related records and malformed values return `400`; duplicate, self, protected, and stale conflicts return `409`.
- Database uniqueness/foreign-key errors do not escape as generic `500` responses.
- Successful batch changes report per-Album outcomes, an aggregate summary, and linked durable Operations.

## Verification

- Run focused Album repository/service/API contract tests.
- Run authentication, Operation, and complete Backend regression suites.
- Run `UI-005` client contract tests after the endpoint is integrated.

## Risks or Notes

- This task intentionally does not define destructive asset lifecycle behavior; that boundary begins with `BT-033`.

## Completion Record

- Extended Album search and date-range query contracts with composable pagination and sorting.
- Added signed zero-write batch preview, explicit overwrite review, atomic stale-checked execution, summaries, and durable Operation linkage.
- Centralized create/update relationship existence, duplicate, and self-reference validation with structured API errors.
- Added repository, service, and authenticated API coverage for query, preview, execution, stale rejection, zero partial write, and relationship failures.
