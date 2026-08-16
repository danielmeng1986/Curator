# AIC-004 — Four-Word Title Placeholder

## Task ID

`AIC-004` — Status: `Complete`

## Goal

Prevent constrained Writer decoding from satisfying a four-word Album title by
appending Roman numerals, repeated letters, or other obvious filler.

## Contract

1. Profile v3 tells the Writer to use a standard four-word placeholder when a
   natural title cannot be completed.
2. The two unique placeholders are `Needs Human Naming Review` and
   `Awaiting Human Naming Review`.
3. Worker normalization replaces Roman-numeral-only and repeated-character
   tail words in the two four-word slots before deterministic validation.
4. Runtime metrics disclose the placeholder policy and replacement count.
5. Existing Profile snapshots and completed Work Items remain immutable.

## Acceptance Criteria

- `Whispers Between Sheets II` becomes `Needs Human Naming Review`.
- A repeated-letter fourth word becomes `Awaiting Human Naming Review`.
- Ordinary four-word titles remain unchanged.
- The resulting six names still satisfy uniqueness and 2/2/3/3/4/4 rules.
