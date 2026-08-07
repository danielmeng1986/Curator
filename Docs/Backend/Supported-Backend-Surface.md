# Supported Backend Surface

## Active entry point

`tools/web_ui/server.py` is the sole runnable Backend entry point. Start it
with `python3 tools/web_ui/server.py`. Its static Web UI assets remain under
`tools/web_ui/static`.

The supported external API boundary is authenticated `/api/v1`, as defined by
the [API Specification](Specifications/API-Specification.md) and the
[API Contract](Specifications/API-Contract.md). No specification declares the
pre-versioned Curator Base App routes as supported.

## Retirement record: BT-016

| Candidate | Classification | Evidence | Result |
| --- | --- | --- | --- |
| `workspace/curator_base_app/server.py` | Retired legacy entry point | Backend Architecture identifies it as the earlier, disabled app and states that its routes are not migration requirements. The API Specification and API Contract define only `/api/v1` as the external client boundary. Repository search found no supported-client invocation outside this historical directory. | Its `main()` now refuses to start, so the pre-versioned Normalize, Import, Albums, and `/api/*` handlers cannot be exposed. Historical source remains for migration reference only. |
| `tools/web_ui/server.py` | Active | It is the newer full Web UI Backend and implements the authenticated `/api/v1` surface covered by the API contract tests. | Retained. |
| `tools/web_ui/server.py` internal `/api/*` compatibility dispatch | Not retired in BT-016 | The current `tools/web_ui/static/api.js` client calls this dispatch directly. Retiring it without a specified client token-configuration migration would break an identified client dependency. | Retained pending an explicitly scoped client migration; it is not the documented supported external API surface. |

## Verification expectations

Run the focused `/api/v1` API regression suite for `tools/web_ui`, and confirm
that invoking `workspace/curator_base_app/server.py` exits without binding a
port. This leaves only the active entry point operational while preserving the
approved versioned API behavior.
