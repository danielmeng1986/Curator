# Curator Backend Server Manual

> Supported application: `apps.backend`  
> Audience: local Server operator and Administrator  
> Last verified: 2026-08-11

<!-- manual-section: purpose -->
## 1. Purpose and supported status

Curator Backend owns the catalog database, file-changing workflows, authentication,
audit records, backup operations, and the static `apps.web` Client. Start this Server
before opening the Web Client. It is a local management service, not a public website.

<!-- manual-section: prerequisites -->
## 2. Prerequisites

- Run commands from the repository root with a supported `python3` environment.
- Ensure the configured database, archive, import, Quarantine, backup, and log locations
  are mounted and writable by the Server account.
- Stop the Backend before applying migrations or replacing/restoring its database.
- Never test maintenance or destructive workflows against the live catalog.

<!-- manual-section: configuration -->
## 3. Configuration and managed paths

Copy `config/backend.example.json` to the ignored `config/backend.json`, then replace
the example absolute paths. Do not commit the local file.

| Setting | Purpose |
| --- | --- |
| `import_source_root` | Root from which reviewed Imports may read |
| `archive_root` | Managed digital-asset archive root |
| `default_import_studio` | Default Studio assigned during Import |
| `quarantine_root` | Optional isolated root for Quarantine operations |

Default runtime locations are `var/data/Curator.db`, `var/backups/`, and `var/logs/`.
Deployments may override them with `CURATOR_DATABASE_PATH`, `CURATOR_RUNTIME_DIR`,
`CURATOR_BACKUP_DIR`, and `CURATOR_LOG_DIR`. `CURATOR_CONFIG_PATH` selects a different
configuration file; `CURATOR_STATIC_DIR` selects the Web Client files; `CURATOR_PORT`
changes the loopback port from `8788`.

Paths and configuration may disclose private asset layout. Tokens and credentials must
be supplied through protected local configuration and must never be committed or pasted
into logs, screenshots, or support reports.

<!-- manual-section: initialize -->
## 4. Initialize or migrate the database

With the Backend stopped and a verified backup available, run the canonical migration:

```bash
python3 -m apps.backend.migrations
```

Use the same configured database path that the Server will use. Do not open SQLite and
apply ad-hoc schema changes. Normal startup refuses a missing database rather than
silently creating a replacement catalog.

<!-- manual-section: lifecycle -->
## 5. Start, verify, stop, and restart

Start the application:

```bash
python3 -m apps.backend
```

Successful startup prints the loopback URL, database path, and backup directory. Open
the printed URL (normally `http://127.0.0.1:8788`) on the same host and verify that the
Curator Client loads. Stop normally with the terminal interrupt (`Ctrl-C`) and wait for
the process to exit. Restart only after the old process has released the port.

Startup creates a database Snapshot and starts daily backup maintenance. A Snapshot
failure is recorded in the backup log; it must be investigated before high-risk work.

<!-- manual-section: bootstrap -->
## 6. Initialize the first Administrator

This is the only supported UI-assisted first-Administrator path. It deliberately needs
local terminal access and works only before an Administrator exists.

1. Start the Backend and open its loopback URL on the same machine.
2. In another terminal, generate a single-use Code:

   ```bash
   python3 -m apps.backend auth create-bootstrap-code
   ```

3. Within ten minutes, enter the Code on **Initialize administrator**, choose the
   Administrator device name, and submit.
4. Copy the issued Admin Token immediately; it is shown once. Store it in an approved
   credential manager, acknowledge storage in the UI, and continue.
5. Confirm that **Administrator Center** is available.

If the Code expires or is consumed, generate a new one. Bootstrap is refused after the
first Administrator exists. Do not use `bootstrap-admin` as an ordinary login or Token
recovery mechanism.

<!-- manual-section: security -->
## 7. Authentication and network safety

The supported Server binds to `127.0.0.1`; keep it loopback-only. Do not publish the
port, add an unreviewed reverse proxy, or weaken authentication to obtain LAN access.
Every device uses an approved role-limited Token. Grant Reader or Writer unless Admin
capabilities are necessary, revoke lost Tokens promptly, and never revoke the final
usable Administrator Token.

<!-- manual-section: recovery -->
## 8. Backup, Snapshot, Restore, and logs

Routine startup/daily Snapshots and their logs live under the configured backup and log
roots. Administrators use **Administrator Center** for catalogued backup, Snapshot
cleanup, and protected database Restore.

Before Restore, verify the selected artifact, review the Preview, read the preflight
result, and enter the required confirmation exactly. Restore is a maintenance operation:
prevent concurrent writes, preserve the pre-Restore Snapshot, and follow the UI result.
Successful database Restore invalidates existing sessions; reconnect using a valid
credential. Never replace the live database file manually while the Server runs.

<!-- manual-section: upgrade -->
## 9. Maintenance and upgrade procedure

1. Announce a write-free maintenance window and stop the Backend.
2. Verify a current recoverable backup and the exact configured database path.
3. Update the application files and configuration examples without overwriting local secrets.
4. Run `python3 -m apps.backend.migrations` once.
5. Start normally and verify the resolved database, backup directory, and loopback URL
   printed by the Server.
6. Reconnect the Client and verify the relevant role workflows and backup status.

Use a historical Workspace archive procedure only when the release notes explicitly say
the database requires it. It is not routine maintenance.

<!-- manual-section: troubleshooting -->
## 10. Troubleshooting

| Symptom | Safe response |
| --- | --- |
| `Database not found` | Check the configured/mounted database path; do not create an empty replacement over the expected catalog. |
| `Static directory not found` | Restore or correctly configure `apps/web/static`; do not point it at an unrelated directory. |
| Port already in use | Stop the prior Curator process or choose an approved `CURATOR_PORT`; do not kill an unidentified process. |
| Bootstrap refused | Confirm no Administrator exists and that Server and command resolve the same database. |
| Bootstrap Code rejected | Generate a new Code locally; Codes are single-use and expire after ten minutes. |
| Token rejected | Confirm the correct Token and device status; ask an Administrator to approve/renew access. Never print Tokens for diagnosis. |
| Backup/Restore failure | Stop high-risk operations, preserve logs and artifacts, and inspect the structured UI result before retrying. |

<!-- manual-section: warnings -->
## 11. High-risk warnings

- Import execution, Repair, Quarantine, Restore, Snapshot cleanup, Token revocation,
  AI Promotion, Group release, and Workspace closure may change durable state.
- Preview is not execution. Recheck the target and impact immediately before confirmation.
- A stale, expired, or already-used Preview must be recreated; never bypass replay checks.
- Preserve operation/audit evidence after partial failure. Do not “fix” state with direct SQL.
- A backup is useful only after its existence and recovery suitability have been verified.

<!-- manual-section: checklist -->
## 12. Verification checklist and Client manuals

- [ ] Configuration resolves only approved local/mounted paths.
- [ ] Migration completes with the Backend stopped.
- [ ] Startup resolves the intended database and static Client.
- [ ] Startup reports the intended loopback URL and creates backup evidence.
- [ ] A role-limited Client can reconnect and sees only permitted workflows.
- [ ] No Token, credential, private path, or asset name was captured in records.

Continue with the [Web Client overview](../client/apps-web/README.md), especially the
[Administrator manual](../client/apps-web/administrator.md) for UI operations.
