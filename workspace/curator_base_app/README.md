# Retired Curator Base App

`workspace/curator_base_app/server.py` is retired and deliberately refuses
to start. Its pre-versioned Normalize, Import, Albums, and `/api/*` routes are
not part of the supported Backend surface.

The source and static files remain only as historical migration reference.
Do not run this directory or add new dependencies on it. Start the active
Backend with:

```bash
python3 tools/web_ui/server.py
```

Supported external clients use authenticated `/api/v1` routes. See
[`Docs/Backend/Supported-Backend-Surface.md`](../../Docs/Backend/Supported-Backend-Surface.md).
