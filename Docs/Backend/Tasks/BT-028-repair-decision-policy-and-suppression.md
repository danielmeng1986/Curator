# BT-028 — Implement Repair Decision Policy and Suppression Records

## Task ID

`BT-028` — Status: `Complete`

## Title

Implement Repair Decision Policy and Suppression Records

## Related Specification(s)

- [Repair Workflow](../Specifications/Repair-Workflow.md), Normative automatic-correction policy, Normative fuzzy path-match evidence, Repair categories, and Error handling, Operations, and Issues.
- [Canonical Path Rules](../Specifications/Canonical-Path-Rules.md), normalization and comparison-key requirements.
- [Operation Logging](../Specifications/Operation-Logging.md), material-work history requirements.
- [Authentication](../Specifications/Authentication.md), administrator authorization model.

## Goal

Provide a service boundary that classifies repair candidates using the specified evidence, permits only the bounded automatic correction, and durably records administrator-controlled rediscovery suppressions.

## Scope

- Implement deterministic classification for automatic canonicalization-only rename, assisted candidate, and manual conflict.
- Validate source/destination roots, component count, normalization equivalence, uniqueness, collision absence, and authoritative fuzzy-match evidence before selecting an action.
- Execute an eligible automatic rename with durable Operation and audit evidence; require confirmation for every other repair category.
- Persist auditable suppression records with fingerprint, bounded scope, reason, creator, timestamps, expiry/review time, and revocation state.
- Apply a suppression only while it is matching, active, and unrevoked; restrict creation, extension, and revocation to administrators.

## Out of Scope

- Moving a conflicting directory to quarantine or restoring it; that belongs to `BT-029`.
- Retention expiry deletion of quarantined content.
- New fuzzy matching heuristics beyond evidence validation defined by the Repair Workflow.

## Dependencies

- `BT-010`, `BT-012`, `BT-013`, and `BT-015` — repair state, Operation, authentication, and Issue boundaries.
- [Repair Workflow](../Specifications/Repair-Workflow.md) — controls all policy decisions.

## Implementation Steps

1. Add repository persistence and migration-safe schema support for suppression records.
2. Implement policy classification and eligible automatic rename execution behind a repair service API, with Operation and audit integration.
3. Implement administrator-only suppression lifecycle and scan-time matching.
4. Add focused repository/service tests for accepted and rejected policy evidence, authorization, expiry, and revocation.

## Acceptance Criteria

- An unconfirmed rename is possible only when every automatic-correction condition is true; the data and database path remain unchanged.
- Interior-whitespace, token, fuzzy, ambiguous, collision, and database-path changes cannot be silently repaired.
- A fuzzy candidate is offered only with all required structural and authoritative evidence; otherwise the case is or remains `ManualConflict`.
- Ignoring a case alone never prevents rediscovery; an active matching suppression does, with durable audit evidence, while expired or revoked records do not.
- Every repair action and suppression administration event has truthful Operation and/or audit context.

## Verification

- Run focused policy, canonical-path, repair, Operation, and authentication tests.
- Resume `BT-022` acceptance scenarios after this task and `BT-029` complete.
- Run the complete Backend regression suite.

## Risks or Notes

- Suppression fingerprints and scopes are durable compatibility contracts; do not derive them from display-only name similarity.
