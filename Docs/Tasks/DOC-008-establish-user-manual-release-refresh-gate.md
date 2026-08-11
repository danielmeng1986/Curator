# DOC-008 — Establish User Manual Release Refresh Gate

## Task ID

`DOC-008` — Status: `Proposed`

## Goal

Make application manual refresh a repeatable milestone/Tag workflow with
deterministic application, role, link, and localization parity checks.

## Scope

- Inventory supported `apps/` entry points and manual coverage.
- Compare en/zh-CN paths, headings, warnings, commands, and internal links.
- Maintain a role/workflow checklist tied to readiness evidence.
- Add a safe release/milestone command and refresh record template.

## Acceptance Criteria

- Missing application, locale file, heading, link, role, or mandatory safety
  section fails with actionable output.
- The gate never starts against or reads production data.
- A release refresh records commit/Tag, evidence, exclusions, and known limitations.
- The gate runs twice cleanly after DOC-006 and DOC-007.

## Dependencies

- DOC-005 through DOC-007.

