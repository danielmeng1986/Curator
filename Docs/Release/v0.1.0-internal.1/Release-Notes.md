# Curator v0.1.0-internal.1 Release Notes

> Release class: Internal deployment · GitHub Pre-release  
> Title: Backend and Web Administration Baseline  
> Release date: 2026-08-12

## Purpose

This source-only baseline lets the project owner reproduce Curator on another
controlled host and test deployment, migration, first-Administrator initialization,
Album-level administration, protected recovery, and AI management workflows.

This is not a public stable distribution. It supplies no installer, binary package,
container image, service supervisor configuration, public-network configuration, or
third-party support promise.

## Included applications

- `apps.backend`: loopback-only Python Backend, versioned REST API, SQLite ownership,
  authentication, Operations/Issues, filesystem workflow control, Snapshots and Restore.
- `apps.web`: static Album-oriented management Client served by the Backend, with
  Reader, Writer, and Administrator capability boundaries.

## Milestone capabilities

- Canonical fresh-database bootstrap and ordered schema migrations.
- First-Administrator local Bootstrap Code and one-time Token handoff.
- Album search/filter/edit/batch workflows and permanent entity management.
- Preview-bound Import execution and paginated Operation history.
- Issue/Repair review, bounded suppression, Repair Quarantine, and item Restore.
- Device registration, role/scopes, renewal, revocation, and final-Admin safety.
- Backend-controlled backup/Snapshot catalog, cleanup, and protected database Restore.
- AI model configurations, Workspaces, exclusive Album Dispatch, photo evidence
  Manifests, two-stage results, review/rework/reject, unique name Promotion, Group
  release, and Workspace closure/archive.
- English and Simplified Chinese Server/Client role manuals.
- Backend, Web contract, Playwright, schema-documentation, and manual release gates.

## Data and upgrade boundary

The Release contains source and documentation only. It contains no catalog database,
backup, Token, credential, local configuration, private asset, model binary, or `var/`
runtime state. Existing databases must be backed up, stopped, and migrated with the
canonical migration command before startup. Never copy a live SQLite database.

## Known limitations

- Supported service exposure is `127.0.0.1` only. LAN/public proxy and TLS deployment
  are not specified or supported by this Release.
- Deployment is manual from source; no installer, service unit, container, or automated
  environment bootstrap is supplied.
- The Web app manages Albums as the digital-asset unit and intentionally has no general
  photo browser. Digital Asset Trash/Purge is not implemented.
- Repair Quarantine is conflict isolation, not Digital Asset Trash.
- The external AI Worker is not packaged as a standalone deployable application here;
  the Release includes the Backend/API and Admin workflow boundary it will use.
- The future macOS native curator application is a Memo, not included software.
- `python3 -m apps.backend --check` is not a supported diagnostic entry point in this
  version; startup output is used to verify resolved runtime paths.

## Deployment and evidence

- Follow the [Deployment Guide](Deployment-Guide.md).
- Review the [Verification Record](Verification-Record.md).
- Application operation is documented in the bilingual
  [User Manuals](../../User-Manual/README.md).

Deployment findings on another host belong in follow-up tasks. The published Tag must
not be moved or amended; corrections use a later prerelease version.
