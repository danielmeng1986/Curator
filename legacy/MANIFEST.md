# Legacy manifest

This directory contains retained historical reference material. It is not part
of Curator's supported runtime surface and must not receive new dependencies.

| Location | Classification | Active replacement |
| --- | --- | --- |
| `scripts/` | Historical database and filesystem migration scripts | `apps/backend` services and migrations |
| `workspace/curator_base_app/` | Retired pre-versioned application | `apps/backend` and `apps/web` |
| `web_ui/` | Retired compatibility launcher and its examples | `python3 -m apps.backend` |

The retained Python entry points are guarded and exit without binding a port or
opening a database. `tools/dev/benchmark/` remains a supported developer tool.
