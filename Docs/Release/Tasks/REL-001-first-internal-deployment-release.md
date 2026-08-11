# REL-001 — First Internal Deployment Release

## Task ID

`REL-001` — Status: `In Progress`

## Release identity

- Version/Tag: `v0.1.0-internal.1`
- Title: `Backend and Web Administration Baseline`
- Class: Internal deployment
- GitHub status: Pre-release
- Distribution: Source archive only; no installer or binary package

## Goal

Publish an immutable, evidence-backed baseline that the project owner can deploy
on another controlled host to test installation, migration, first-Administrator
initialization, Album administration, recovery, and AI management workflows.

## Included scope

- Supported `apps.backend` and `apps.web` applications.
- Canonical database bootstrap/migrations and current schema documentation.
- Reader, Writer, and Administrator authentication/authorization boundaries.
- Album/entity, Import, Operation, Issue/Repair, Quarantine, backup/Restore,
  AI Workspace, Work Dispatch, review, rework, and Promotion management.
- English and Simplified Chinese application manuals.
- Backend, Web contract, UI readiness, Playwright, schema-doc, and manual gates.

## Explicit exclusions

- Public installer, container image, package repository, or service supervisor unit.
- Public/LAN exposure, reverse-proxy/TLS configuration, or multi-user support promise.
- Database, backup, Tokens, credentials, private paths/assets, model binaries, or `var/` state.
- General photo browsing, Digital Asset Trash/Purge, macOS native Curator, and a
  separately packaged AI Worker.

## Deliverables

- `Docs/Release/v0.1.0-internal.1/Release-Notes.md`.
- `Docs/Release/v0.1.0-internal.1/Deployment-Guide.md`.
- `Docs/Release/v0.1.0-internal.1/Verification-Record.md`.
- Completed user-manual release refresh record.
- Release commit, annotated Tag, pushed remote state, and GitHub Pre-release.

## Acceptance criteria

- All gates required by the Release Specification pass against the candidate.
- Clean-host guide distinguishes new database initialization from existing database migration.
- First-Admin, backup, Restore, rollback, secrets, and loopback-only boundaries are explicit.
- Release documents identify limitations without implying public support.
- Local/remote annotated Tag targets the verified release commit.
- GitHub Release title/version match and it is marked Pre-release.

## Execution order

1. Verify branch, remote, dependency/runtime baseline, and repository cleanliness.
2. Write release notes, deployment guide, and refresh/verification records.
3. Run complete Backend and Web acceptance plus documentation gates.
4. Commit the release candidate and record its commit identity.
5. Create and verify annotated Tag `v0.1.0-internal.1`.
6. Push the release commit and Tag; create the GitHub Pre-release.
7. Verify remote publication and mark this task Complete.

## Follow-up deployment trial

Deploy the published source archive/Tag on another controlled host. Record environment,
time-to-first-start, migration/bootstrap outcome, workflow smoke results, and every
manual or portability gap as new owning tasks. Do not amend or move the released Tag.
