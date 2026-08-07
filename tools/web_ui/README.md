# Curator Web UI Compatibility Area

The active Web Client has moved to `apps/web`. This directory retains only the
temporary compatibility launcher and its local runtime configuration example.

## Start

```bash
python3 -m apps.backend
```

Open **http://127.0.0.1:8080** in a browser.

`python3 tools/web_ui/server.py` remains a temporary compatibility launcher;
it delegates to the Backend while preserving the old local runtime paths.

## Backend configuration

The authoritative Backend reads `config/backend.json`; copy it from
`config/backend.example.json` and set the local source/archive paths. Its
runtime database, backups, and logs are under `var/` by default.

## Transitional launcher configuration

Copy `tools/web_ui/app_config.example.json` to the ignored local file
`tools/web_ui/app_config.json`, then edit it:

```json
{
  "import_source_root": "/path/to/source",
  "archive_root": "/path/to/archive",
  "default_import_studio": "MetArt"
}
```

This is a transitional configuration location used only by the compatibility
launcher. MT-005 retires this location after the active replacements are
verified.

## Tech Stack

- Python 3 stdlib HTTP server (no external dependencies)
- Vanilla HTML/CSS/JS SPA with hash-based routing
- SQLite via `sqlite3` module
- Automatic daily DB backups with 15-day retention
