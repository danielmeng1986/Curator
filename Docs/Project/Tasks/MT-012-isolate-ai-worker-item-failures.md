# MT-012 — Isolate AI Worker Item Failures

## Task ID

`MT-012` — Status: `Complete`

## Title

Continue the AI Worker After Isolated Invalid Model Output

## Goal

Prevent one recoverable Album Work Item failure from stopping the continuous AI
Worker, while retaining truthful Failed state and stopping after repeated or
systemic failures.

## Scope

- Identify the exact invalid Writer title, word-count problem, capitalization
  problem, or forbidden word in local validation diagnostics.
- Feed the exact validation failure back into bounded Writer retries and tell the
  model not to repeat the rejected title or forbidden word.
- Mark an exhausted Work Item Failed, then continue to the next compatible item.
- Reset the consecutive failure counter after a successful Work Item.
- Stop after a configurable number of consecutive recoverable item failures;
  default to three.
- Continue to stop immediately for invalid Worker configuration, incompatible
  executables, model/projector/accelerator initialization, kind mismatch,
  authorization, and other non-transient Backend errors.
- Document queue recovery and the deliberate Retry action for Failed items.

## Out of Scope

- Automatically retrying a Failed Work Item at the Backend level.
- Changing claim, lease, Failed, Pending, Retry, Cancel, or Group closure states.
- Silently accepting titles that violate the Backend Writer contract.
- Editing existing Work Item configuration snapshots.

## Runtime Contract

1. A recoverable item error is reported to Backend and leaves that item Failed.
2. Continuous mode logs the bounded failure, increments the consecutive count,
   and claims the next Pending item.
3. One successful item resets the consecutive count to zero.
4. The process stops after `--max-consecutive-item-failures`, default `3`.
5. `--once` still exits unsuccessfully when its one claimed item fails.
6. Systemic and security-sensitive failures remain immediately terminal.
7. Restarting a compatible Worker resumes Pending items automatically; a Failed
   item is claimed only after an Administrator explicitly selects Retry.

## Acceptance Criteria

- A title containing `Session` identifies both the complete rejected title and
  the forbidden word in the Work Item failure.
- Corrective Writer retries contain the specific failure and prohibit repeating
  it.
- One or two consecutive `MODEL_OUTPUT_INVALID` items do not stop continuous
  processing when the configured limit is three.
- A successful item between failures resets the counter.
- Three consecutive recoverable item failures stop the process with an
  actionable message.
- Global configuration and non-transient API errors stop immediately.
- Unit tests and the Chinese Worker operating procedure cover recovery.

## Verification

- `python3 -m unittest workers.ai_worker.tests.test_worker`
- Manual sequence: invalid Writer output → Failed → next Pending item starts →
  fix deployed → Backend and Worker restarted → Administrator Retry → item
  returns to Pending and is processed.

## Completion Record

- Added rule-specific Writer validation and corrective feedback.
- Added the configurable consecutive-item failure circuit breaker with success
  reset and systemic-failure exceptions.
- Added regression coverage and queue recovery guidance on 2026-08-17.
