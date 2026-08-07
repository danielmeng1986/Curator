# Supported Backend Surface

## Active entry point

`apps/backend` is the sole authoritative runnable Backend. Start it with
`python3 -m apps.backend`. Its static Web UI assets are under `apps/web/static`.

Historical launchers are retained under `legacy/` only and refuse to start.

The supported external API boundary is authenticated `/api/v1`, as defined by
the [API Specification](Specifications/API-Specification.md) and the
[API Contract](Specifications/API-Contract.md). No specification declares the
pre-versioned Curator Base App routes as supported.

## Retirement record: BT-016

| Candidate | Classification | Evidence | Result |
| --- | --- | --- | --- |
| `workspace/curator_base_app/server.py` | Retired legacy entry point | Backend Architecture identifies it as the earlier, disabled app and states that its routes are not migration requirements. The API Specification and API Contract define only `/api/v1` as the external client boundary. Repository search found no supported-client invocation outside this historical directory. | Its `main()` now refuses to start, so the pre-versioned Normalize, Import, Albums, and `/api/*` handlers cannot be exposed. Historical source remains for migration reference only. |
| `apps/backend` | Active | It owns the authenticated `/api/v1` surface, API adapter, Services, Repositories, infrastructure, bootstrap, and regression tests. | Authoritative entry point. |
| `legacy/web_ui/server.py` | Retired compatibility launcher | MT-005 moved it to the legacy manifest after active replacement verification. | Its `main()` refuses to start. |
| `apps/backend` internal `/api/*` compatibility dispatch | Transitional server compatibility | MT-003 moved the active Web Client to authenticated `/api/v1`; no active client depends on this dispatch. | It is not a documented external API surface and may be retired only by a separately scoped Backend task. |

## Verification expectations

Run the focused `/api/v1` API regression suite through `apps/backend`, confirm
that `tools/web_ui/server.py --check` delegates to the new Backend, and confirm
that invoking `workspace/curator_base_app/server.py` exits without binding a
port. This leaves one active Backend implementation while preserving the
approved versioned API behavior.
