# MT-015 — Repair Writer Slots and Regenerate Vision

## Task ID

`MT-015` — Status: `Complete`

## Goal

Resolve persistent Writer failures without discarding valid titles, while
providing an explicit, auditable higher-cost path that resamples Album evidence
and re-runs both Vision and Writer.

## Scope

- Keep ordinary **Retry Writer** as an `AwaitingWriter` resume operation.
- Preserve valid title slots and regenerate only duplicated, forbidden,
  malformed, or filler-conflicted slots with bounded per-slot generation.
- Add Admin-only **Re-run From Vision** for Failed `AwaitingWriter` items.
- Preserve the failed Work Item, Manifest, and Vision; mark it Cancelled and
  create a Pending successor in the same Dispatch Group.
- Give the successor durable lineage, generation number, and selection seed.
- Prioritize previously unused eligible images in its new immutable Manifest.
- Limit a lineage to three Vision regenerations and reject resampling when no
  additional eligible images exist.

## Runtime Contract

1. Retry Writer never replaces an accepted Vision or Manifest.
2. Slot repair retains every valid unique title byte-for-byte.
3. Re-run From Vision creates a new Work Item; predecessor results are never
   deleted or overwritten.
4. The predecessor becomes Cancelled and the successor begins at
   `AwaitingVision` at the end of the queue.
5. Seed, generation, predecessor Manifest, and overlap count are retained in
   the successor Manifest discovery summary.

## Acceptance Criteria

- One invalid title causes one-title generation rather than a six-title replay.
- A successor selects a different sample when alternatives exist.
- UI distinguishes Retry Writer from Re-run From Vision and explains cost and
  lineage before confirmation.
- Backend, Worker, migration, API/UI contract, and browser regressions pass.

## Verification

- `python3 -m unittest workers.ai_worker.tests.test_worker`
- `python3 -m unittest apps.backend.tests.test_services`
- `python3 -m unittest apps.backend.tests.test_migrations apps.backend.tests.test_api_contract`
- `node apps/web/tests/work_dispatch_ui_contract_test.mjs`
- Work Dispatch browser acceptance.

## Completion Record

- Added invalid-slot Writer repair, immutable successor lineage, seeded
  fresh-first Evidence sampling, and explicit UI controls on 2026-08-18.
