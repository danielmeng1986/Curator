# Curator AI Worker

The Worker is an out-of-process API client. Configure `CURATOR_API_URL` and
`CURATOR_DEVICE_TOKEN` in its environment; never place tokens or database paths
in source. It may call authenticated read endpoints and generate local,
suggestion-only analysis. It must not open SQLite, import Backend code, or
access historical `workspace_album`. It may claim, heartbeat, and fail a
Backend-created Album AI Work Item through the dedicated REST API. Persisting
Vision/Writer results remains disabled until the two-stage submission contract
is implemented.
