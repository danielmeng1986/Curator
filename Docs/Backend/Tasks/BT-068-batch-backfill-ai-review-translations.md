# BT-068 — Batch Backfill AI Review Translations

## Task ID

`BT-068` — Status: `Blocked`

## Title

Add Administrator-Reviewed Historical Translation Backfill

## Blocker

Implementation begins only after `BT-067/UI-038` is used on a representative
sample and the Administrator explicitly accepts DeepL translation quality.

## Goal

Populate missing Simplified Chinese Recommendation translations across retained
AI Review history without retranslating cached text or changing immutable AI
results.

## Scope

- Admin-only Preview reporting Work Items, unique missing texts, cached texts,
  character count, configured quota/readiness, remaining one-time Developer
  allowance or Growth-period allowance, and bounded batch size.
- Explicit Execute using a signed, expiring, single-use reviewed scope.
- Chunked, resumable processing through the `BT-067` adapter/cache, with rate
  limiting, progress, cancellation between chunks, and durable Operation
  evidence.
- Idempotent restart, per-chunk results, partial/failure truth, and no duplicate
  provider charge for committed cache hits.

## Out of Scope

- Automatic scheduled translation, translating non-Recommendation fields, or
  changing Review/Promotion state.
- Admin browser workflow, owned by `UI-039`.

## Acceptance Criteria

- Preview is zero-write and states exact eligible/missing/cached scope and
  character impact before external calls.
- Execute translates only the bound missing hashes and can resume safely.
- Quota/timeout/cancellation produces truthful partial progress; cached success
  remains reusable and no unprocessed item is claimed successful.
- Database results remain derived cache data, never AI result mutations.

## Verification

- Fake-provider batch, quota, cancellation, replay, concurrency, and restart
  acceptance against a disposable database.
- Complete Backend and `UI-039` browser regression.
