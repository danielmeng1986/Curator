# Supported Backend Surface

## Active entry point

`apps/backend` is the sole authoritative runnable Backend. Start it with
`python3 -m apps.backend`. Its static Web UI assets remain temporarily under
`tools/web_ui/static` until MT-003 moves the client.

`tools/web_ui/server.py` remains a temporary compatibility launcher. It
delegates to `apps.backend` while preserving its prior local database,
configuration, log, backup, static-file paths, and port behavior. It contains
no API, Service, Repository, or database implementation.

The supported external API boundary is authenticated `/api/v1`, as defined by
the [API Specification](Specifications/API-Specification.md) and the
[API Contract](Specifications/API-Contract.md). No specification declares the
pre-versioned Curator Base App routes as supported.

## Retirement record: BT-016

| Candidate | Classification | Evidence | Result |
| --- | --- | --- | --- |
| `workspace/curator_base_app/server.py` | Retired legacy entry point | Backend Architecture identifies it as the earlier, disabled app and states that its routes are not migration requirements. The API Specification and API Contract define only `/api/v1` as the external client boundary. Repository search found no supported-client invocation outside this historical directory. | Its `main()` now refuses to start, so the pre-versioned Normalize, Import, Albums, and `/api/*` handlers cannot be exposed. Historical source remains for migration reference only. |
| `apps/backend` | Active | It owns the authenticated `/api/v1` surface, API adapter, Services, Repositories, infrastructure, bootstrap, and regression tests. | Authoritative entry point. |
| `tools/web_ui/server.py` | Transitional launcher | It delegates to the active Backend so the legacy local command continues to work during MT-003. | Retire in MT-005 after client migration verification. |
| `apps/backend` internal `/api/*` compatibility dispatch | Not retired in BT-016 | The current `tools/web_ui/static/api.js` client still calls this dispatch. Retiring it without a specified client token-configuration migration would break an identified client dependency. | Retained pending MT-003; it is not the documented supported external API surface. |

## Verification expectations

Run the focused `/api/v1` API regression suite through `apps/backend`, confirm
that `tools/web_ui/server.py --check` delegates to the new Backend, and confirm
that invoking `workspace/curator_base_app/server.py` exits without binding a
port. This leaves one active Backend implementation while preserving the
approved versioned API behavior.
