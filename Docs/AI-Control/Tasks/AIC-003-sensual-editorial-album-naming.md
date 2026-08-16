# AIC-003 — Sensual Editorial Album Naming

## Task ID

`AIC-003` — Status: `Complete`

## Goal

Improve Writer recommendations for the adult Album dataset so names create
intrigue and imaginative tension instead of reading like neutral descriptions,
content labels, production notes, or anatomical inventories.

## Contract

1. Preserve constrained Writer JSON and the ordered 2/2/3/3/4/4 word-count rule.
2. Prefer sensual, provocative, imaginative editorial naming built from mood,
   invitation, tension, metaphor, atmosphere, and elegant wordplay.
3. Reject in the prompt—not by inventing unsupported visual facts—literal
   combinations of clothing, anatomy, pose, room, media category, and shooting
   terminology.
4. Avoid clinical, mechanical, pornographic, and production-label phrasing.
5. Do not describe explicit sexual acts or identify a person.
6. Publish the change as immutable default Profile version 2. Historical Work
   Items retain their original version 1 snapshot.

## Acceptance Criteria

- New Model Configurations and migrated configurations resolve Profile v2.
- Existing Work Item snapshots remain unchanged.
- Writer constrained decoding and deterministic validation remain unchanged.
- Profile composition tests demonstrate the new positive style direction and
  negative vocabulary guidance.
