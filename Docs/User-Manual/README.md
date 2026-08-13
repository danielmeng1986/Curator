# Curator Application User Manuals

> Documentation status: Approved
> Owner: Project documentation
> Last verified: 2026-08-11

This directory contains role-oriented operating manuals for supported
applications under `apps/`. The controlled structure, language parity, tooling
exclusion, safety rules, and release refresh process are defined in the
[User Manual Specification](Specification.md).

## Current delivery status

| Application | Category | English | 简体中文 |
| --- | --- | --- | --- |
| `apps.backend` | Server | [English](en/server/apps-backend.md) | [简体中文](zh-CN/server/apps-backend.md) |
| `apps.web` | Client | [English](en/client/apps-web/README.md) | [简体中文](zh-CN/client/apps-web/README.md) |
| `workers.ai_worker` | External AI Worker | [English](en/worker/ai-worker.md) | [简体中文](zh-CN/worker/ai-worker.md) |

Supported `apps/` applications and explicitly identified external Worker
runtimes are listed. The AI Worker is a headless WSL2 API client with its own
least-privilege Writer identity.
Developer scripts under `tools/` are not user-manual applications.

## Milestone and release refresh

At every application milestone and before creating a release Tag:

1. Copy and complete the [Release Refresh Record template](Release-Refresh-Record-Template.md).
2. Recheck supported entry points, role/navigation changes, high-risk workflows,
   browser acceptance evidence, known limitations, and English/Chinese content.
3. Run the read-only documentation gate twice:

   ```bash
   python3 tools/check_user_manuals.py
   ```

The gate reads repository documentation and application entry-point files only. It does
not start the Server, access the catalog database, or execute a user workflow. A failed
check blocks the documentation refresh until corrected or assigned to the owning BT,
UI, MT, or DOC task.
