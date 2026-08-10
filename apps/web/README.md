# Curator Web Client

The Web Client is static source served by the Curator Backend. Start the
Backend with `python3 -m apps.backend`, then open its loopback address.

All client requests use authenticated `/api/v1`. Select **Connect** in the
header to save an optional Backend URL and an approved device token in the
current browser profile. Neither value is embedded in source, and a missing or
invalid token stops the request before any client-side fallback can write data.

The historical `workspace_album` UI is intentionally absent. Active AI work is
handled by the dataset-specific Work Dispatch and AI Review pages; historical
rows cannot be reopened through the client.

Run the browserless client contract check with:

```bash
node apps/web/tests/api_contract_test.mjs
```

## Test layers

Install the pinned Node dependencies and the default browser once:

```bash
npm ci
npm run playwright:install
```

Use the fast contract layer during development:

```bash
npm run test:web:contract
```

Run the real Chromium smoke gate for each completed UI task:

```bash
npm run test:web:e2e
```

Before a release, install all supported browsers and run the cross-browser gate:

```bash
npm run playwright:install:all
npm run test:web:e2e:all-browsers
```

The Playwright runner starts a disposable Backend fixture and never uses live
Curator data. Successful runs remove their temporary traces, screenshots, and
videos. Failed runs print the isolated artifact directory. Existing focused
scripts in `apps/web/tests/*_browser_acceptance.mjs` remain detailed workflow
gates; Backend and API tests remain authoritative for business rules and error
contracts.

Run the complete release-readiness UI gate twice before release:

```bash
npm run test:ui-readiness
```

This command runs ten mandatory suites with startup checks, isolation, explicit
timeouts, task/Specification/Backend evidence in its summary, and no implicit
skips. A failure retains a sanitized artifact directory; complete success
removes the temporary gate directory.
