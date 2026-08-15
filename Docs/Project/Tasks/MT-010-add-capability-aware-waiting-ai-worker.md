# MT-010 — Add a Capability-Aware Waiting AI Worker

## Task ID

`MT-010` — Status: `Complete`

## Title

Run the AI Worker as a Capability-Declared Long-Poll Client

## Related Specification(s)

- [Backend Architecture](../../Backend/Backend-Architecture.md), out-of-process
  AI Worker API-client boundary.
- [API Specification](../../Backend/Specifications/API-Specification.md),
  capability-aware long-poll claim contract proposed by `BT-063`.
- [Authentication](../../Backend/Specifications/Authentication.md), Writer
  Device identity and Token lifecycle.

## Goal

Let an operator start an AI Worker explicitly as an Album Name Analysis Worker
and leave it running so future compatible Dispatches are claimed and executed
automatically, promptly, and safely over outbound HTTP.

## Scope

- A required `--worker-kind album_name_analysis` run option backed by a local
  registry of supported Worker workflows.
- Capability declaration on every claim request.
- Bounded long-poll waiting instead of the fixed empty-queue sleep loop.
- Immediate processing of an atomically claimed compatible Work Item followed by
  renewal of the next wait request.
- Defensive validation that the returned Work Item kind matches the selected
  local workflow before evidence or model execution begins.
- Automatic reconnect with bounded exponential backoff and jitter after network
  interruption, Backend restart, or long-poll transport failure.
- Graceful Ctrl-C while waiting or processing and preservation of `--once` as a
  non-waiting smoke run.
- Redacted lifecycle diagnostics, unit tests, disposable real-HTTP acceptance,
  and bilingual deployment-manual updates.

## Out of Scope

- Opening an HTTP listener or firewall port in WSL2.
- Receiving Backend webhooks, SSE, or WebSocket messages.
- Storing Worker kind as a permanent Device registration attribute.
- Claiming multiple Worker kinds in one process in the first implementation.
- Concurrent inference within one Worker process.
- Installing or starting the Worker as a systemd or Windows Task Scheduler
  service; the manual may describe that as a separate operator step.
- Advertising model inventory, GPU capacity, load, or performance estimates.

## Dependencies

- `MT-009` — runnable, enrollable WSL2 AI Worker lifecycle.
- `BT-063` — finalized capability-aware long-poll claim API and audit contract.
- The controlling Backend specifications must be amended and `BT-063` marked
  `Ready` before this task can move to `Ready`.

## Runtime Contract

1. The supported command explicitly selects one local workflow:

   ```bash
   python3 -m workers.ai_worker run --worker-kind album_name_analysis \
     --llama-cli /path/to/llama-mtmd-cli --model-root /path/to/models
   ```

2. Startup rejects an unknown Worker kind before making a claim or touching
   evidence.
3. Every normal claim declares exactly the selected Worker kind and waits for
   at most the Backend-supported long-poll bound.
4. A normal empty timeout immediately starts the next wait and is not logged as
   an error.
5. `--once` performs one immediate, non-waiting compatible claim. It processes at
   most one item and exits successfully when none is available.
6. A claimed item with a missing or mismatched `worker_kind` is never processed.
   The Worker reports a bounded, truthful protocol/configuration failure only if
   it actually owns the incompatible claim, then stops rather than guessing a
   workflow.
7. Transport errors use bounded exponential backoff with jitter; authentication,
   authorization, invalid configuration, and unsupported-contract errors fail
   visibly instead of retrying forever.
8. Ctrl-C during a long poll exits cleanly. Ctrl-C during a claim preserves the
   existing lease semantics and never falsely submits completion.
9. Device Token, evidence paths, prompts containing private data, and model-local
   secrets remain absent from command arguments and logs.

## Implementation Steps

1. Add a Worker-kind registry that binds `album_name_analysis` to the existing
   Analysis workflow and rejects unknown kinds during startup validation.
2. Extend the API client claim payload with the selected capability and bounded
   wait duration.
3. Replace fixed empty-queue sleeping with consecutive long-poll claims and add
   categorized reconnect/backoff behavior.
4. Validate returned Work Item kind before resolving model configuration,
   preparing evidence, or invoking llama.cpp.
5. Preserve heartbeat, failure reporting, temporary evidence cleanup, two-stage
   submission, `--once`, and graceful shutdown behavior.
6. Add deterministic unit tests for CLI validation, payloads, empty timeout,
   reconnect/backoff, mismatch, Ctrl-C, and no-secret diagnostics.
7. Extend disposable Backend acceptance to start a waiting Worker before
   Dispatch and prove automatic progress to `ReadyForReview` afterward.
8. Update English and Chinese AI Worker manuals with the explicit kind,
   always-running behavior, expected waiting output, recovery, and optional
   host-service guidance.

## Acceptance Criteria

- A documented command starts an approved WSL2 process explicitly as
  `album_name_analysis` and waits without opening an inbound port.
- When an Administrator Dispatches compatible work after the Worker is already
  waiting, it begins processing without another operator command or manual
  refresh.
- The Worker never claims work under an undeclared kind and never processes a
  returned mismatched kind.
- Normal long-poll timeout is quiet and immediately renewable; transient Backend
  or network interruption reconnects with bounded backoff and no busy loop.
- Authentication, revocation, unsupported kind, missing model, and invalid local
  configuration remain terminal and actionable.
- `--once` remains suitable for a controlled smoke run and does not wait for a
  future Dispatch.
- Existing lease heartbeat, Evidence integrity/cleanup, Vision/Writer schema,
  failure reporting, and Ctrl-C guarantees remain intact.
- A disposable real-HTTP test proves: Worker starts first → queue is empty →
  Admin Dispatches → Worker is awakened and claims → result reaches
  `ReadyForReview`.

## Verification

- `python3 -m unittest workers.ai_worker.tests.test_worker` plus new capability,
  wait, reconnect, and CLI lifecycle tests.
- Disposable real-HTTP Backend workflow with Dispatch occurring after the Worker
  has entered its wait.
- Backend claim concurrency and authorization suites from `BT-063`.
- Manual Windows 11/WSL2 smoke verification using `--once` and continuous modes.

## Risks or Notes

- Long polling makes execution prompt but does not keep the process alive across
  Windows or WSL restart. Reliable unattended hosting remains an operator/service
  concern and may warrant a later dedicated task.
- The initial single-kind process is intentional. Supporting several kinds in
  one process requires explicit workflow/provider compatibility and scheduling
  policy rather than accepting an arbitrary list at the CLI.

## Completion Record

- Added required `--worker-kind album_name_analysis` startup selection and a
  local workflow registry that rejects unsupported kinds before claim.
- Replaced fixed empty-queue sleeping with renewable bounded long polls;
  `--once` remains one immediate compatible claim and exits cleanly when empty.
- Added bounded exponential reconnect backoff with jitter for transient
  transport failures while leaving authentication, authorization, and contract
  failures terminal.
- Added returned-kind validation before evidence/model access, truthful mismatch
  failure reporting, and retained heartbeat, cleanup, two-stage submission, and
  Ctrl-C behavior.
- Updated English/Chinese deployment guidance and unit/real-HTTP regression
  coverage. Completed on 2026-08-15 with all release gates passing.
