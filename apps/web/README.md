# Curator Web Client

The Web Client is static source served by the Curator Backend. Start the
Backend with `python3 -m apps.backend`, then open its loopback address.

All client requests use authenticated `/api/v1`. Select **Connect** in the
header to save an optional Backend URL and an approved device token in the
current browser profile. Neither value is embedded in source, and a missing or
invalid token stops the request before any client-side fallback can write data.

The historical `workspace_album` UI is intentionally absent. That collection
is being closed and archived by MT-008; a future dataset-specific Workspace UI
requires its own Specification and API.

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
