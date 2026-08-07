# Curator AI Worker

The Worker is an out-of-process API client. Configure `CURATOR_API_URL` and
`CURATOR_DEVICE_TOKEN` in its environment; never place tokens or database paths
in source. It may call authenticated read endpoints and generate local,
suggestion-only analysis. It must not open SQLite, import Backend code, access
`workspace_album`, or persist AI results until a dedicated AI Workspace API is
specified.
