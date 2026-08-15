# Curator AI Worker

The Worker is a supported out-of-process API client. It runs with:

```bash
python3 -m workers.ai_worker --help
```

Use `enroll` to create a dedicated WSL2-owned Writer identity, `status` after
Admin approval, and `run --worker-kind album_name_analysis` to wait for and
process compatible Work Items. Private state defaults
to `~/.config/curator/ai-worker.json` with mode `0600`.

The Worker never opens SQLite, imports Backend code, reads an Album path, or
accesses historical `workspace_album`. It claims and heartbeats a Backend-created
Album AI Work Item, asks the Backend to select an immutable Evidence Manifest,
downloads bounded images only by opaque evidence UUID, runs llama.cpp, then
submits ordered `vision/v1` and `writer/v1` results. Submission is claim-bound
and idempotent. Admin Review and Promotion remain outside the Worker.

See the [deployment manual](../../Docs/User-Manual/en/worker/ai-worker.md) or
[简体中文部署手册](../../Docs/User-Manual/zh-CN/worker/ai-worker.md).
