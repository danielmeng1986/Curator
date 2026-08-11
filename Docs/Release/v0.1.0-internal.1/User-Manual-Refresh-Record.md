# v0.1.0-internal.1 Application Manual Release Refresh Record

## Target

- Milestone/release: Backend and Web Administration Baseline
- Candidate commit or Tag: `v0.1.0-internal.1` (candidate)
- Review date: 2026-08-12
- Reviewer: Release owner with Codex-assisted evidence collection

## Supported application inventory

| Application | Category | Supported entry point | Status/change |
| --- | --- | --- | --- |
| `apps.backend` | Server | `python3 -m apps.backend` | Included; loopback-only |
| `apps.web` | Client | Served by `apps.backend` from `apps/web/static` | Included; Reader/Writer/Admin |

## Change review

- [x] Application entry points and supported runtime assumptions were rechecked.
- [x] Routes, navigation labels, role/scopes, and disclosure behavior were rechecked.
- [x] Authentication and first-Administrator instructions were rechecked.
- [x] Preview/Execute, destructive, backup/Restore, and failure behavior were rechecked.
- [x] Ready workflows were added; blocked/retired workflows are not presented as usable.
- [x] English and Simplified Chinese files were updated together.
- [x] Tools remain excluded except for documented application-operation commands.

## Acceptance evidence

- User-manual gate command/result: `python3 tools/check_user_manuals.py` passed twice;
  5 mirrored manuals across 2 mandatory locales
- Safe command checks performed: migration and supported entry points covered by existing acceptance/manual evidence
- Browser acceptance suites/results: Web contract 5/5; UI readiness 10/10 suites;
  default Chromium Playwright smoke 1/1
- Related tasks: DOC-005 through DOC-008; REL-001

## Known limitations and exclusions

- Known limitations: loopback/source-only deployment; unavailable Digital Asset Trash;
  standalone AI Worker and macOS curator not included.
- Intentionally excluded: generic `tools/` scripts, tests as user workflows, runtime
  databases/backups/logs, Tokens, local configuration, assets, and model binaries.
- Follow-up: second-host deployment trial; new tasks will own discovered gaps.

## Approval

- [x] Documentation matches the application candidate and release Tag contents.
- [x] No Token, credential, private path, production data, or sensitive diagnostic is embedded.
- [x] Release owner accepts the documented internal-release limitations.

Decision: Pass for Tag creation; remote publication verification remains in REL-001.
