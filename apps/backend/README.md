# Curator Backend

The authoritative Backend entry point is:

```bash
python3 -m apps.backend
```

Copy `config/backend.example.json` to the ignored local file
`config/backend.json` and set the archive/import paths before running a real
workflow. By default, the Backend resolves runtime data beneath `var/`:

```text
var/data/Curator.db
var/backups/
var/logs/
```

`CURATOR_DATABASE_PATH`, `CURATOR_CONFIG_PATH`, `CURATOR_RUNTIME_DIR`,
`CURATOR_LOG_DIR`, `CURATOR_BACKUP_DIR`, and `CURATOR_STATIC_DIR` provide
explicit local or deployment overrides. The static client is served from
`apps/web/static`.

Run regressions with:

```bash
python3 -m apps.backend.tests.run_regression all
```

Apply reviewed database migrations explicitly (with the Backend stopped):

```bash
python3 -m apps.backend.migrations
```

`tools/web_ui/server.py` is a compatibility launcher only. It delegates to
this package with the old local runtime locations until the client migration is
complete.
