# AIC-005 — Natural Title Word Counts

## Task ID

`AIC-005` — Status: `Complete`

## Goal

Prefer natural Album titles over mechanically filling a four-word slot.

## Contract

1. Produce six unique ordered names: two words, two words, three words, three
   words, then three or four words for each of the final two slots.
2. A natural three-word title is valid in either trailing slot.
3. Grammar-constrained decoding structurally enforces these choices.
4. If an older model output appends a Roman numeral or repeated-letter filler
   to a trailing title, the Worker removes that final word and retains the
   natural three-word title.
5. Worker and Backend accept the equivalent distribution independent of order:
   exactly two 2-word names, at least two 3-word names, and trailing diversity
   made from natural 3-or-4-word names.
6. Historical Profile and Work Item snapshots remain immutable; Profile v4 is
   used only by future Dispatches.

## Acceptance Criteria

- `Whispers Between Sheets II` normalizes to `Whispers Between Sheets`.
- `Silken Shadows Unveiled IIIIIIIIIIIIIIIIIIIIIIII` normalizes to
  `Silken Shadows Unveiled`.
- Natural four-word titles remain valid.
- Six-name uniqueness and capitalization rules remain enforced.
