# UI-039 — Administer AI Review Translation Backfill

## Task ID

`UI-039` — Status: `Blocked`

## Title

Review and Run Historical AI Recommendation Translation Backfill

## Blocker

Requires explicit translation-quality approval plus completed `BT-068`.

## Goal

Provide an Administrator Center workflow for previewing and running bounded,
resumable translation backfill after on-demand DeepL quality is accepted.

## Scope

- Show provider readiness, usage/quota summary, cached/missing Work Items,
  unique source texts, character estimate, and bounded batch controls.
- Require fresh Preview and explicit confirmation before starting paid external
  work.
- Show durable progress, succeeded/cached/failed counts, cancellation boundary,
  restart guidance, and Operation links.
- Never display, accept, or modify the DeepL API key.

## Acceptance Criteria

- No batch begins without reviewed Backend scope and explicit confirmation.
- Refresh/restart resumes from durable progress and never repeats committed
  cache work.
- Partial provider failure is shown truthfully and does not affect AI Review or
  Promotion state.
- The screen clearly states that translations are machine-generated assistance.

## Verification

- Disposable fake-provider browser acceptance for preview, execute, progress,
  interruption, retry, quota failure, and cache reuse.
