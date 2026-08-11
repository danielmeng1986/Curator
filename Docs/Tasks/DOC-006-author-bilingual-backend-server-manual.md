# DOC-006 — Author Bilingual Backend Server Manual

## Task ID

`DOC-006` — Status: `Complete`

## Goal

Publish matched English and Chinese operator manuals for `apps.backend`.

## Scope

- Prerequisites, configuration, managed paths, canonical migration, startup and health.
- First-Admin Bootstrap Code and loopback initialization handoff.
- Bind/network/authentication safety, logs, backup/Snapshot/Restore and maintenance.
- Observable troubleshooting, high-risk warnings, and verification checklist.

## Out of Scope

- General developer/test tools and raw API reference.
- apps.web workflow instructions beyond links to Client manuals.

## Deliverables

- `Docs/User-Manual/en/server/apps-backend.md`.
- `Docs/User-Manual/zh-CN/server/apps-backend.md`.

## Acceptance Criteria

- Commands are supported by app entry points and verified on disposable resources.
- English/Chinese headings, warnings, workflows, and links are equivalent.
- No instruction opens SQLite directly or weakens migration/recovery contracts.

## Dependencies

- DOC-005.
