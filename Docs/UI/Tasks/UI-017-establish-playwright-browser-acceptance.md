# UI-017 — Establish Playwright Browser Acceptance Infrastructure

## Task ID

`UI-017` — Status: `Complete`

## Title

Establish Reproducible Playwright Browser Acceptance Infrastructure

## Related Specification(s)

- [UI Verification Strategy](../Verification-Strategy.md).
- [UI Workflow Readiness Matrix](../Workflow-Readiness-Matrix.md).
- [UI-003](UI-003-establish-browser-workflow-fixtures.md).

## Goal

Make real-browser UI acceptance reproducible from a clean checkout while
preserving fast Backend, API, and client-contract feedback layers.

## Scope

- Pin Playwright and its test runner in the repository dependency lockfile.
- Provide an isolated Chromium smoke gate over the disposable Backend fixture.
- Provide an opt-in Chromium, WebKit, and Firefox release gate.
- Capture screenshots, traces, video, console errors, page errors, and failed
  requests only when useful for failure diagnosis.
- Document commands and the responsibility boundary between contract and
  real-browser tests.

## Out of Scope

- Rewriting all existing focused browser workflows into runner-style specs.
- Visual-regression baselines, load testing, or production-data testing.
- Installing browser binaries implicitly during ordinary test execution.

## Dependencies

- UI-003 — supplies isolated Backend, roles, Tokens, cleanup, and redaction.
- Existing focused browser acceptance scripts — remain workflow-level gates.

## Implementation Steps

1. Add pinned Node dependencies, Playwright configuration, and install/run commands.
2. Add a runner-based Chromium smoke test using the disposable entity fixture.
3. Preserve failure evidence outside repository/runtime data and remove it on success.
4. Run contract, smoke, focused browser, and relevant Backend regressions.

## Acceptance Criteria

- A clean checkout has a deterministic command to install dependencies and Chromium.
- The default E2E gate exercises a real Chromium browser against a disposable Backend.
- The release command selects Chromium, WebKit, and Firefox without changing tests.
- A successful run removes temporary artifacts; a failed run reports their isolated path.
- Browser diagnostic attachments redact fixture Tokens and registration secrets.
- Fast contract tests remain separately runnable and do not require a browser.

## Verification

- `npm run test:web:contract`.
- `npm run test:web:e2e` twice from clean disposable state.
- Existing focused Playwright workflow smoke test.
- Relevant Backend authenticated workflow regression.

## Risks or Notes

- Browser binaries are substantial machine-local dependencies and are intentionally
  installed through explicit commands.
- The default developer/feature gate uses Chromium; all-browser execution is a
  release gate so ordinary feedback remains fast.

## Completion Record

- Added repository-pinned Playwright `1.62.1` dependencies and a deterministic
  lockfile; the installed dependency tree passes `npm audit` with zero findings.
- Added separate browserless-contract, Chromium feature-gate, and opt-in
  Chromium/WebKit/Firefox release commands.
- Added a runner-based Writer connection and permanent Album-management smoke
  journey over the UI-003 disposable entity fixture.
- Added isolated failure-only screenshots, traces, video, and sanitized browser
  diagnostics. Successful runs remove their unique temporary artifact root.
- Verified the contract layer, two consecutive clean Chromium runs, the existing
  focused browser workflow smoke, and the authenticated Backend workflow on
  2026-08-11.
