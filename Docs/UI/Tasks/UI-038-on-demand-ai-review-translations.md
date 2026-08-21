# UI-038 — On-Demand AI Review Translations

## Task ID

`UI-038` — Status: `Ready`

## Title

Show Cached Simplified Chinese Assistance Below AI Recommendation Titles

## Related Specification(s)

- [UI Specification](../Specification.md), AI Review and interruption behavior.
- [Work Dispatch Workflow](../../Backend/Specifications/Work-Dispatch-Workflow.md).
- `BT-067` and `UI-027`.

## Goal

Reduce AI Review reading time by letting an Administrator translate the current
Recommendation list on demand and display each cached Chinese translation on a
second line beneath its unchanged English title.

## Scope

- Add **Show Chinese translations** beside AI Recommendations.
- On click, request Backend-owned translations for the current Work Item; never
  call DeepL from browser code.
- Render English on line one and Chinese on line two, preserving the existing
  radio selection and English Promotion value.
- Add **Hide Chinese translations** without deleting cache data.
- Automatically render already cached translations on later visits without an
  external request; distinguish cached, loading, unavailable, and retryable
  failure states.
- Label translations as machine-generated review assistance.
- Preserve Review drafts, selected Recommendation, keyboard workflow, next-item
  navigation, and stale-version handling.

## Out of Scope

- Editing a machine translation or promoting it as the Album name.
- Automatic translation on initial page load.
- Historical bulk translation or provider administration; owned by `BT-068`
  and `UI-039` after quality approval.

## Acceptance Criteria

- Before opt-in, the page behaves exactly as today and makes no translation
  request.
- One click translates all current Recommendation titles; every translated
  option uses a two-line English/Chinese layout.
- Radio selection and approval/Promotion submit the original English value.
- Refresh/revisit uses persisted cache and does not require DeepL availability.
- Simple titles can remain untranslated by leaving the control unused.
- Provider/configuration failure is local to translation assistance and never
  blocks Review, draft save, approval, rejection, rework, or navigation.
- Controls remain Admin-only and accessible by keyboard/screen reader.

## Verification

- UI contract test for English authority, two-line layout, and Backend-only API.
- Disposable browser journey with a fake provider: opt-in, cache reuse after
  refresh, selection/approval unchanged, and provider failure isolation.
- AI Review draft, Promotion, permission, and live-navigation regressions.
