# MT-009 — Add a Runnable AI Worker

## Task ID

`MT-009` — Status: `Completed`

## Title

Package the AI Worker as a Supported WSL2 Runtime

## Related Specification(s)

- [Backend Architecture](../../Backend/Backend-Architecture.md), AI Worker API-client boundary.
- [Authentication](../../Backend/Specifications/Authentication.md), trusted-LAN and Writer Token rules.
- [API Specification](../../Backend/Specifications/API-Specification.md), claim, evidence, heartbeat, failure, and two-stage result contracts.

## Goal

Turn the existing `workers/ai_worker` client/provider foundation into a
supported command that can run continuously in WSL2 Ubuntu 24.04, claim work,
maintain leases, process Manifest evidence, and submit validated Vision and
Writer results without direct database or managed-path access.

## Scope

- A documented module or console entry point with configuration validation.
- A headless device-enrollment command that generates and retains the candidate
  Device Token inside WSL2, submits a Registration Proof request, checks delayed
  approval, and activates the same least-privilege Writer credential.
- Polling/backoff, claim ownership, periodic heartbeat, graceful shutdown, and
  truthful failure reporting.
- Evidence download to bounded temporary storage and guaranteed cleanup.
- llama.cpp executable/model configuration, two-stage prompt/result adapters,
  structured redacted logs, and exit behavior.
- Install/dependency metadata plus fake-provider and disposable-Backend tests.
- Windows 11 WSL2 Ubuntu 24.04 operating and upgrade instructions.

## Out of Scope

- Direct SQLite, archive-root, or Album-path access.
- Admin Review, Promotion, Group release, or Workspace closure.
- Automatic Token approval or embedding credentials in files/source.
- Declaring a single production model or GPU backend for every host.

## Dependencies

- MT-004 Worker API-client foundation.
- BT-046–049 claim, evidence, and two-stage result contracts.
- An approved decision for supported Worker configuration keys and result
  generation/parsing behavior.

## Implementation Steps

1. Specify the Worker process lifecycle, configuration source, result adapters,
   temporary-data policy, and observable failure states.
2. Add the supported entry point and package/dependency metadata.
3. Implement polling, heartbeat, signal handling, retries, cleanup, and
   redacted diagnostics around the existing client/provider boundary.
4. Add fake-provider unit tests and a disposable Backend end-to-end Worker run.
5. Promote the deployment manual from preparation-only to runnable procedure.

## Acceptance Criteria

- One documented command starts the Worker and Ctrl-C stops it without a
  traceback, leaked claim ownership, or retained evidence files.
- One documented enrollment command obtains Admin-approved Writer access
  without copying a browser-owned Device Token or exposing plaintext in process
  arguments, logs, shell history, or repository files.
- Missing/invalid URL, Token, executable, model, or configuration fails before
  claiming work and never prints a credential.
- Backend/model interruption maintains or truthfully fails the lease according
  to policy; no item is falsely reported complete.
- Vision then Writer submission uses the production schemas and an approved
  Writer Token; the Worker cannot perform Admin actions.
- A disposable end-to-end test reaches `ReadyForReview` without direct database
  access from the Worker process.

## Verification

- `python3 -m unittest workers.ai_worker.tests.test_worker` plus new lifecycle
  and disposable-Backend suites.
- Manual Windows 11/WSL2 smoke verification after automated acceptance passes.
- Backend workflow/readiness regression.

## Risks or Notes

- llama.cpp CLI compatibility remains dependent on the operator-selected build;
  preflight and a `--once` smoke run are required after runtime/model updates.

## Completion Record

- Added `python3 -m workers.ai_worker` with headless `enroll`, delayed-approval
  `status`, and continuous/`--once` `run` commands. Private identity state is
  atomically stored with mode `0600` and Tokens are never passed in arguments.
- Added configuration/path preflight, llama.cpp multimodal invocation, bounded
  JSON extraction, polling, heartbeat, retrying inference, Evidence hash/size
  verification, mode-`0600` temporary files, cleanup, two-stage submission,
  truthful failure reporting, and graceful Ctrl-C.
- Extended the Backend evidence-manifest contract so only Admin or the exact
  active Writer claim owner can ask the Backend to select/read a Manifest; the
  Worker still cannot nominate or discover filesystem paths.
- Worker unit tests and a disposable real-HTTP Backend workflow prove claim,
  Worker-created Manifest, opaque Evidence transfer, runtime cleanup, Vision,
  Writer, and `ReadyForReview` without Worker database access.
- Verification completed with 9 Worker unit tests, 34 Workflow Readiness tests,
  4 focused AI Workspace workflow tests, 768 complete Backend regression tests,
  and two successful bilingual manual-gate runs.
