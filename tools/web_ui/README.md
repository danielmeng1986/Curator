# Curator Web UI

Full-featured local web interface for Curator, implementing the spec from `Docs/UI/`.

## Start

```bash
python3 tools/web_ui/server.py
```

Open **http://127.0.0.1:8080** in a browser.

## Features

| Page | Route | Description |
|---|---|---|
| Dashboard | `#/` | Entity counts, recent operations |
| Albums | `#/albums` | Browse/search/filter permanent albums |
| Album Detail | `#/albums/:id` | Edit album, manage models/relations/photos |
| Models | `#/models` | Browse/create/edit models |
| Studios | `#/studios` | Browse/create/edit studios |
| Workspace | `#/workspace/albums` | Browse and batch-edit workspace albums |
| Import | `#/import/albums` | Multi-step import from folders to permanent albums |
| Statuses | `#/statuses` | Admin controlled-status list |

## Configuration

Edit `tools/web_ui/app_config.json`:

```json
{
  "import_source_root": "/path/to/source",
  "archive_root": "/path/to/archive",
  "default_import_studio": "MetArt"
}
```

## Tech Stack

- Python 3 stdlib HTTP server (no external dependencies)
- Vanilla HTML/CSS/JS SPA with hash-based routing
- SQLite via `sqlite3` module
- Automatic daily DB backups with 15-day retention
