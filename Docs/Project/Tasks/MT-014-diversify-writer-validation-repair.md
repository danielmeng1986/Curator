# MT-014 — Diversify Writer Validation Repair

## Task ID

`MT-014` — Status: `Complete`

## Title

Prevent Deterministic Replay of Invalid Writer Names

## Goal

Make bounded Writer validation repair produce a genuinely distinct attempt and
prevent Worker normalization from creating duplicate suggested names.

## Scope

- Derive a bounded Writer seed from Work Item UUID, Backend attempt count, and
  internal generation attempt, and pass it explicitly to `llama-cli`.
- Preserve configured temperature for the first generation and use reviewed
  low temperature `0.1` only for corrective generations.
- Include repair attempt number and the previous `suggested_names` in validation
  feedback so consecutive repair prompts are not identical.
- Reject filler removal when it would create a duplicate title.
- Record effective Writer attempt, seed, and temperature in opt-in private debug
  metadata and result metrics.

## Out of Scope

- Relaxing the six-unique-name Backend contract.
- Automatically accepting or inventing replacement titles outside the model.
- Retrying an administratively Failed Work Item without an explicit UI Retry.
- Changing accepted Vision results or Backend replay protection.

## Runtime Contract

1. Initial Writer generation retains the configured temperature.
2. Each internal corrective attempt receives a different prompt and seed.
3. A later Backend Retry receives a different seed because its claim attempt
   count changes.
4. Corrective temperature never exceeds the existing reviewed maximum `0.2`.
5. Title normalization either preserves uniqueness or reports a specific
   validation error; it never manufactures a duplicate.
6. Raw output remains opt-in and private; metadata contains only non-secret
   generation controls.

## Acceptance Criteria

- `llama-cli` receives `--seed` for every Writer generation.
- Two corrective attempts cannot have identical attempt controls.
- A zero-temperature initial generation uses `0.1` during correction.
- The observed `Water's Embrace Serenity II` collision is rejected before
  normalization can turn it into a duplicate.
- Worker unit and integration tests pass.

## Verification

- `python3 -m unittest workers.ai_worker.tests.test_worker`
- Manual Retry with `--model-debug-dir`: compare each Writer metadata file's
  `generation.attempt`, `generation.seed`, and `generation.temperature`.

## Implementation Record

- Implemented attempt-aware Writer sampling, targeted repair feedback, and
  collision-safe title normalization on 2026-08-18.
- Automated Worker tests passed before operator Retry validation.
- WSL debug metadata confirmed distinct effective seeds and corrective
  temperatures on 2026-08-18; MT-015 addresses the remaining model-level title
  repetition with invalid-slot repair.
