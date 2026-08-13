# UI-003 — Establish Browser Workflow Fixtures

## Task ID

`UI-003` — Status: `Complete`

## Title

Establish Disposable Browser Workflow Fixtures

## Related Specification(s)

- [UI Verification Strategy](../Verification-Strategy.md).
- [Backend Testing Strategy](../../Backend/Testing-Strategy.md).
- [MT-006](../../Project/Tasks/MT-006-ui-workflow-acceptance.md).

## Goal

Extend the existing disposable browser gate into deterministic scenario
fixtures for all UI workflows without accessing live Curator resources.

## Scope

- Builders for Reader, Writer, and Admin devices and token lifecycle states.
- Entity, Import, Operation, Issue, Repair, Quarantine, Snapshot, and future Workspace fixtures.
- Disposable database, source/destination filesystem, archive, backup, log, and output roots.
- Per-scenario cleanup plus screenshots, console output, and operation identifiers on failure.

## Out of Scope

- Production-data testing or performance/load certification.
- Encoding business decisions only to make a fixture convenient.

## Dependencies

- UI-001 — defines scenario inventory.
- Existing `apps/web/tests/disposable_backend.py` and Playwright gate.

## Implementation Steps

1. Define a scenario-builder API and isolated test composition root.
2. Add deterministic data/filesystem factories and role/token helpers.
3. Prove cleanup, parallel isolation where supported, and two consecutive clean runs.

## Acceptance Criteria

- Tests never open live database, media, archive, token, backup, or output paths.
- A failed or interrupted scenario leaves no reusable credential and no shared mutable fixture.
- Fixtures can create both successful and specified invalid states without bypassing Service rules except for clearly labelled historical setup.
- Failure artifacts contain no plaintext Token or registration secret.

## Verification

- Run fixture self-tests and the existing browser smoke test twice from clean state.
- Run Backend workflow-readiness afterward to prove isolation.

## Risks or Notes

- Filesystem workflow fixtures must use explicit temporary roots, never paths derived from the live configuration.
- The AI Workspace scenario is now `Ready`; it uses the approved UI-011A/B and
  BT-043 through BT-058 contracts and remains wholly disposable.

## Completion Record

- Replaced the in-memory smoke composition root with an on-disk disposable
  Backend whose database, source, archive, Snapshot, Quarantine, Backup, log,
  and output resources all live beneath one unique temporary root.
- Added reusable scenario and Reader/Writer/Admin device builders, authenticated
  request helpers, explicit failure-artifact directories, secret redaction, and
  shutdown cleanup assertions.
- Added empty, permanent-entity, workflow-evidence, filesystem, and AI Workspace
  scenarios. The latter was activated only after its approved Backend schema,
  dispatch, review, and read-model contracts existed.
- Migrated the existing browser smoke gate to the shared fixture and proved two
  clean entity-fixture runs with unique roots and rejected-write side effects.
