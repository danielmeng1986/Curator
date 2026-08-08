# BT-049 — Implement Two-Stage AI Result Submission Contract

## Task ID

`BT-049` — Status: `Proposed`

## Title

Validate and Persist Vision Analysis and Album-Name Recommendations

## Related Specification(s)

- UI-011A AI Collection Workspace Specification, two-stage result schema.
- `config/ai.toml` Vision and Writer output schemas.

## Goal

Accept versioned, Manifest-bound AI output in two ordered stages and persist
truthful analysis and name recommendations on `workspace_album_ai_worker`.

## Scope

- Stage-one Album analysis JSON covering observable scene, people count/range,
  location/environment, subjects, objects, actions, confidence, and warnings.
- Stage-two summary/description and bounded unique `suggested_names` JSON.
- JSON Schema versions, payload/field limits, English/format rules where approved,
  Work Item state guards, configuration/Manifest binding, idempotency, and validation errors.
- Raw accepted output, normalized read model, runtime metrics, and Operation evidence.

## Out of Scope

- Judging model quality, human review, or updating permanent Album data.
- Accepting model prose outside the versioned JSON contract.

## Dependencies

- BT-046 through BT-048.
- Approved UI-011A JSON schemas and suggested-name count (currently benchmarked as six).

## Implementation Steps

1. Publish versioned Vision and Writer JSON Schemas based on current benchmark prompts.
2. Implement ordered, claim-bound submission and normalized persistence.
3. Add malformed, oversized, duplicate, replay, wrong-stage, stale-Manifest, and success tests.

## Acceptance Criteria

- Recommendation submission cannot precede an accepted analysis result.
- Results bind to the exact Work Item, configuration snapshot, and evidence Manifest.
- Duplicate idempotent submission returns the same outcome; conflicting replay is rejected.
- Invalid JSON or name constraints produce no Ready-for-Review state.

## Verification

- Schema corpus tests, Worker/API integration tests, Operation assertions, and full regression.

## Risks or Notes

- The existing prompt requests exactly six names while earlier discussion used
  five as an example; UI-011A must make the count configurable or freeze it.
