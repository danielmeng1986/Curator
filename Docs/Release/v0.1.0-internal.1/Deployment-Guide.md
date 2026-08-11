# v0.1.0-internal.1 Deployment Guide

> Audience: project owner deploying on another controlled host  
> Distribution: source-only internal Pre-release

## 1. Safety boundary

Keep the Backend on `127.0.0.1`. Do not expose it through a LAN/public bind, port
forward, or unreviewed reverse proxy. Do not bring Tokens, databases, model files,
private assets, or machine-local configuration into Git.

For an existing catalog, stop all writers and make a verified backup before copying or
migrating. Never copy a live SQLite database and never repair it with ad-hoc SQL.

## 2. Host prerequisites

- Git client with access to `https://github.com/danielmeng1986/Curator`.
- Python 3.10 or newer for the supported application entry point. The Release candidate
  was verified with Python 3.14.5.
- A modern browser on the same host as the loopback Backend.
- Writable local/mounted locations for catalog data, backups, logs, Import source,
  archive, and optional Quarantine.
- Node.js/npm are not required to run Curator. They are required only to reproduce Web
  acceptance tests; the candidate used Node.js 22.17.0 and npm 10.9.2.

## 3. Obtain the immutable source

After the Release is published:

```bash
git clone https://github.com/danielmeng1986/Curator.git
cd Curator
git checkout v0.1.0-internal.1
```

Confirm `git status --short` is empty and `git describe --tags --exact-match` reports
`v0.1.0-internal.1`. Do not deploy from a moving branch when testing this baseline.

## 4. Create local configuration

Copy `config/backend.example.json` to `config/backend.json` and replace every example
with an absolute path on the new host. The local file is ignored by Git. Configure:

- `import_source_root` for reviewed Import input;
- `archive_root` for managed Album assets;
- `default_import_studio` for Import defaults;
- optional `quarantine_root` when Repair Quarantine is used.

Default runtime paths are under `var/`. Prefer explicit host-local environment values
when data lives elsewhere: `CURATOR_DATABASE_PATH`, `CURATOR_RUNTIME_DIR`,
`CURATOR_BACKUP_DIR`, `CURATOR_LOG_DIR`, `CURATOR_CONFIG_PATH`, and
`CURATOR_STATIC_DIR`. Never store a Token in these committed examples.

## 5. Prepare the database

### New deployment

Choose the final database and backup paths first. With the Backend stopped, run:

```bash
python3 -m apps.backend.migrations
```

The ordered migration path creates the current schema. Confirm the expected database
and a migration backup/verification record exist before startup.

### Existing catalog migration

1. Stop the old Backend and every Worker/client that can write.
2. Copy the database only after shutdown to the new host using a protected channel.
3. Preserve and verify a separate pre-upgrade backup.
4. Configure Curator to resolve the copied database and intended backup root.
5. Run `python3 -m apps.backend.migrations` once while the Backend remains stopped.
6. Preserve migration output. Do not continue if integrity, foreign-key, or backup
   verification fails.

Historical Workspace archival is not routine deployment. Use it only if release/migration
evidence explicitly identifies an applicable historical schema.

## 6. Start and initialize access

Start Curator from the repository root:

```bash
python3 -m apps.backend
```

Verify the printed URL is loopback (normally `http://127.0.0.1:8788`) and that the
database and backup paths are the intended new-host locations. Open the URL locally.

For a genuinely new catalog with no Administrator, generate a local one-time Code:

```bash
python3 -m apps.backend auth create-bootstrap-code
```

Within ten minutes choose **Initialize administrator** in the UI, enter the Code and a
device name, then copy the one-time Admin Token into approved secure storage. Do not
run first-Admin bootstrap on a migrated catalog that already has an Administrator.

## 7. Deployment smoke test

1. Reconnect with the intended Admin Token and open **Administrator Center**.
2. Verify **Backups and Snapshots** reports a startup recovery point or an actionable
   failure; create/verify an Admin Snapshot before high-risk testing.
3. Confirm **Albums**, **Models**, **Studios**, **Statuses**, **Operations**, and
   **Issues** load without changing data.
4. Use disposable/non-production items for any Import, Repair, Quarantine, Dispatch,
   Promotion, or Restore acceptance. Review each Preview and resulting Operation.
5. Verify Reader/Writer Tokens see only their allowed navigation and Backend scope.
6. Stop normally with `Ctrl-C` and confirm the process exits before host maintenance.

## 8. Optional acceptance reproduction

Install pinned test-only dependencies without changing the lock file:

```bash
npm ci
npx playwright install chromium
python3 -m apps.backend.tests.run_regression all
npm run test:web:contract
npm run test:ui-readiness
npm run test:web:e2e
python3 tools/check_schema_docs.py
python3 tools/check_user_manuals.py
```

These tests use disposable fixtures; do not redirect them to the deployed catalog.

## 9. Upgrade, rollback, and evidence

Before upgrading from this Tag, stop writes, verify a current backup, read the target
Release notes, and execute its migration procedure. If deployment fails, stop the new
Backend, preserve logs/Operations, restore the verified pre-upgrade recovery point using
the protected recovery procedure, and check out the previous immutable Tag. Do not move
Tags or overwrite failure evidence.

Record the second-host operating system, Python version, path/mount differences,
database origin, time-to-first-start, first-Admin/migration result, smoke workflows, and
manual gaps. Never include real Tokens, private asset names, or private absolute paths.
