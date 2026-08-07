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
