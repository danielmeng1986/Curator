# UI Verification Strategy

> Documentation status: Current
> Owner: UI
> Last verified: 2026-08-13

This document describes evidence layers, disposable fixtures, diagnostic
handling, and readiness gates. Normative workflow behavior belongs to
`Specification.md`.

## Purpose

UI verification proves that accepted Backend capabilities form complete,
truthful browser workflows. This document assigns evidence to test layers; it
does not duplicate the interaction, recovery, security, or confirmation rules
in the [UI Specification](Specification.md).

## Evidence layers

| Layer | Responsibility |
| --- | --- |
| Backend unit/service/workflow/API tests | Authoritative business rules, authorization, state transitions, durable side effects, idempotency, and zero-write rejection. |
| Browserless Web contract tests | Request/response mapping, role-sensitive rendering, field behavior, component contracts, and fast interaction logic. |
| Focused Playwright journeys | Complete visible workflow, navigation, modal, refresh, browser-state, and cross-role behavior against disposable Backend resources. |
| UI readiness gate | Required suite inventory, timeouts, interruption-dimension declarations, sanitized evidence, and final pass/fail reporting. |
| Optional release engine gate | Chromium plus WebKit and Firefox parity where release policy requires it. |

The lowest layer capable of proving a rule owns the exhaustive cases. Browser
tests demonstrate orchestration and user-visible recovery; they do not repeat
every Backend validation permutation.

## Fixture isolation

Real-browser tests use disposable databases, archive roots, source trees,
backups, Snapshots, Tokens, registration material, model configuration records,
and output directories. They never read or mutate live Curator data.

Every rejected, cancelled, stale, replayed, conflicting, or unauthorized
material action includes a durable or filesystem zero-unintended-side-effect
assertion at the appropriate layer. Destructive and recovery scenarios do not
share mutable fixtures unless isolation is independently proven.

## Workflow and interruption coverage

Each readiness suite declares the applicable Specification boundaries:

- modal close;
- navigation;
- refresh;
- browser restart;
- Backend restart;
- delayed action or another actor;
- retry and stale/replay handling;
- cancellation or abandonment; and
- client upgrade/cache behavior.

A boundary is either covered by named evidence or marked not applicable with a
concrete reason. A missing applicable boundary cannot be reported as Ready.
One uninterrupted happy path is exploratory evidence, not workflow acceptance.

## Diagnostics and secrecy

On failure, the browser infrastructure may retain screenshots, traces, video,
console errors, page errors, failed-request summaries, and a sanitized artifact
location. Successful disposable artifacts are removed.

Diagnostics must never contain plaintext Tokens, candidate credentials,
registration proofs/secrets, Bootstrap Codes, token hashes, sensitive recovery
paths, or prohibited Backend diagnostics. Tests verify both rendered output and
network payload disclosure where role boundaries differ.

## Readiness and release evidence

`npm run test:ui-readiness` executes the manifest-owned required suites. The
runner performs preflight validation, applies per-suite timeouts, continues the
audit after an individual failure, removes successful artifacts, and exits
non-zero if any required suite fails.

The [Workflow Readiness Matrix](Workflow-Readiness-Matrix.md) is the living
human-readable result. It records current classification and evidence ownership
without embedding volatile total Backend test counts. Dated audits preserve the
conditions observed at a particular time and must not replace the living matrix.
