# BT-063 — Capability-Aware Long-Poll Work Claim

## Task ID

`BT-063` — Status: `Complete`

## Title

Match Worker Capabilities and Wake Long-Poll Claims After Dispatch

## Related Specification(s)

- [API Specification](../Specifications/API-Specification.md), Work Item claim,
  lease, and failure contracts.
- [Work Dispatch Workflow](../Specifications/Work-Dispatch-Workflow.md), Worker
  kind, Dispatch execution, and Work Item creation.
- [Authentication](../Specifications/Authentication.md), least-privilege Writer
  Device identity and Token scopes.

## Goal

Let an approved Writer Worker wait for and atomically claim only Work Items that
match the capabilities of its currently running process, so a later Dispatch
wakes compatible Workers promptly without opening an inbound Worker endpoint or
binding work permanently to one Device.

## Scope

- An immutable required `worker_kind` on every dispatch-created Work Item,
  including migration/backfill of existing Album-analysis Work Items.
- A versioned claim request that requires a bounded list of Worker kinds
  supported by the calling process and accepts a bounded long-poll timeout.
- Atomic claim selection filtered by required Worker kind, Workspace lifecycle,
  run state, and existing lease-expiry rules.
- Backend wake-up of waiting claims after committed compatible Work Item
  creation, with timeout and disconnect cleanup.
- A timeout response representing “no compatible work” without creating an
  attempt or Operation.
- Persistence of the process capability declaration as an immutable snapshot on
  each successful attempt/claim audit record.
- Concurrency, authorization, migration, restart, timeout, and lost-wakeup tests.
- Corresponding amendments to the controlling API and Work Dispatch
  specifications before this task may move to `Ready`.

## Out of Scope

- Backend callbacks, webhooks, or inbound ports on Worker hosts.
- WebSocket or Server-Sent Events transport.
- Permanently storing runtime capabilities as part of Device registration.
- Selecting or permanently assigning a Dispatch to a particular Device.
- Device-level `allowed_worker_kinds` policy.
- Model-file discovery, GPU scheduling, load balancing, capacity advertisement,
  or proof that a Worker has a particular model installed.
- Replacing claim leases, heartbeat ownership, retry, or failure contracts.

## Dependencies

- `BT-046` — atomic Work Item claims, leases, attempts, and retries.
- `BT-054` and `BT-056` — registered Worker kinds and atomic Dispatch execution.
- `BT-059` — canonical schema bootstrap and ordered migration practice.
- `BT-061` — approved client-owned Writer Device Tokens.
- `MT-010` consumes this contract in the runnable AI Worker after the Backend
  portion is available.

## Contract Decisions

1. Device identity remains an authorization boundary only: approved Writer role,
   `read`/`write` scopes, expiry, rotation, disablement, and revocation.
2. Runtime capability is declared by the Worker process on every claim request;
   it is not inferred from the Device name and is not persisted as permanent
   Device configuration.
3. The initial capability dimension is `worker_kind`. The first registered and
   executable value is `album_name_analysis`.
4. A claim request contains `worker_kinds` as a non-empty, unique, bounded list
   of Backend-registered values. Unknown or malformed values receive a
   structured `400` response.
5. `wait_seconds` is an integer from 0 through 30. Zero performs an immediate
   claim attempt; a positive value waits for compatible work until the deadline.
6. A successful response contains an already atomically claimed Work Item. A
   notification alone never grants ownership and is never returned as work.
7. Multiple compatible waiting Workers may be awakened, but database-level
   atomic claim rules ensure that one Work Item has only one active owner.
8. The Backend records the normalized `worker_kinds` declaration with the
   successful attempt. No attempt or claim audit record is created on timeout.
9. Work Item `worker_kind` is immutable and copied from the registered Dispatch
   adapter at creation. Existing Album-analysis rows are backfilled as
   `album_name_analysis` with migration evidence.
10. Dispatch commit is the wake-up boundary. Rollback must not publish runnable
    work; missed or process-local notifications remain safe because every wait
    cycle checks durable queue state before sleeping and again before timeout.
11. Timeout, client disconnect, Backend restart, or notification loss may delay
    delivery but may not lose, duplicate, or transfer claim ownership.

## Implementation Steps

1. Amend the API and Work Dispatch specifications with the capability, timeout,
   response, audit, and no-inbound-callback contract; resolve any schema naming
   conflicts before marking the task `Ready`.
2. Add canonical schema and migration support for immutable Work Item
   `worker_kind` and attempt capability snapshot data.
3. Extend claim validation and repository selection to match registered Worker
   kinds while preserving transaction-level ownership and lease expiry.
4. Add a bounded in-process wait/notification coordinator suitable for the
   current single Backend process, with durable rechecks that preserve
   correctness across restarts and missed notifications.
5. Notify compatible waiters only after successful Dispatch commit and return a
   normal empty result at the long-poll deadline.
6. Add structured metrics or redacted diagnostics for waiting, timeout,
   successful matching, and invalid capability declarations without logging
   Tokens.
7. Add focused service/API/migration tests and real-HTTP concurrent Worker
   acceptance.

## Acceptance Criteria

- A Writer declaring `album_name_analysis` can wait on one authenticated outbound
  HTTP request and receive a compatible Work Item promptly after a later
  Dispatch.
- A Writer that does not declare the Work Item's required kind cannot claim it,
  even when it is the oldest Pending item.
- One incompatible item at the head of the queue does not block claiming a later
  compatible item.
- Under simultaneous compatible claims, each Work Item is owned by at most one
  Token and every successful claim has exactly one attempt record.
- Claim attempts preserve existing Workspace, lease-expiry, Token ownership,
  heartbeat, evidence, and result-submission rules.
- Timeout creates no Work Item mutation, attempt, Operation, or false failure.
- The successful attempt retains the normalized runtime capability declaration
  used to make the match.
- Disabled, revoked, expired, non-Writer, or insufficient-scope Devices cannot
  wait for or claim work.
- Backend restart and client reconnect preserve durable Pending work and do not
  require an inbound Worker port.
- Existing Album-analysis Work Items are migrated deterministically and remain
  claimable only by the corresponding declared kind.

## Verification

- Schema inventory and empty/existing-database migration checks.
- Service and repository tests for filtering, bounds, lease expiry, queue order,
  timeout, and audit snapshots.
- Real-HTTP tests for Dispatch-during-wait, incompatible waiting Workers,
  simultaneous claims, disconnect, and Backend restart/reconnect.
- Complete Backend, Work Dispatch, AI Workspace, authentication, and evidence
  regressions.

## Risks or Notes

- The current Backend is a single `ThreadingHTTPServer` process, so an in-process
  condition coordinator is sufficient for prompt wake-up but cannot be the
  correctness boundary. Durable database rechecks are mandatory and preserve a
  future move to multiple Backend processes.
- Long polling consumes one server thread per waiting Worker. The 30-second bound
  is acceptable for the expected small trusted-LAN Worker fleet; larger fleets
  should trigger an asynchronous transport/server review rather than silently
  increasing the timeout.
- Runtime capability declarations describe process behavior; they do not grant
  additional authorization beyond the approved Writer Token.

## Completion Record

- Amended the controlling API and Work Dispatch specifications before changing
  implementation behavior.
- Added ordered migration `0016` for immutable Work Item `worker_kind`,
  deterministic Album-analysis backfill, the queue index, and attempt capability
  snapshots.
- Added capability validation, atomic kind-filtered claims, bounded 0–30 second
  waiting, commit-time compatible wake-up, durable rechecks, and zero-write
  timeout behavior.
- Added migration, service, real-HTTP Dispatch-during-wait, authorization,
  validation, incompatible-head, and audit-snapshot coverage.
- Completed on 2026-08-15; the 690-test Backend/Worker regression and complete
  15-suite UI readiness gate passed.
