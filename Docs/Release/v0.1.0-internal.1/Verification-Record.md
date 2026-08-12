# v0.1.0-internal.1 Verification Record

> Status: Published and Verified
> Verification date: 2026-08-12  
> Release class: Internal deployment Pre-release

## Candidate identity

- Branch: `main`
- Preparation baseline: `93a35b857b1efb2bc9455b4c5953cd0c997c4c1f`
- Application/release-governance candidate: `93a35b857b1efb2bc9455b4c5953cd0c997c4c1f`
- Tag target: the release-record commit containing this file; verified through the annotated Tag
- Tag: `v0.1.0-internal.1` (annotated and published)
- Remote: `https://github.com/danielmeng1986/Curator.git`
- Prior published milestone Tag: `milestone-backend-web-foundation-2026-08-08`

## Verification environment

- Host context: controlled project development host
- Python: 3.14.5
- Node.js: 22.17.0
- npm: 10.9.2
- Playwright: 1.62.1
- Browser gate: default Chromium

## Required gate results

| Gate | Command | Result |
| --- | --- | --- |
| Backend regression | `python3 -m apps.backend.tests.run_regression all` | Pass — 764 tests |
| Web contracts | `npm run test:web:contract` | Pass — 5 tests |
| UI readiness | `npm run test:ui-readiness` | Pass — 10 required suites |
| Playwright acceptance | `npm run test:web:e2e` | Pass — Chromium smoke, 1 test |
| Schema documentation | `python3 tools/check_schema_docs.py` | Pass — 44 tables, 15 migrations |
| User manuals, pass 1 | `python3 tools/check_user_manuals.py` | Pass — 5 mirrored manuals, 2 locales |
| User manuals, pass 2 | `python3 tools/check_user_manuals.py` | Pass — identical second run |
| Diff/secret/repository review | reviewed release candidate | Pass — no diff whitespace or embedded release secret found |

## Publication checks

- [x] Version and Release class comply with the Release Specification.
- [x] GitHub authentication and repository remote were confirmed.
- [x] Local and GitHub Release/Tag names were unoccupied before preparation.
- [x] Release documents and User Manual refresh record are complete.
- [x] Worktree was clean after the final release candidate commit.
- [x] Annotated local Tag resolves to `aa545fb255b0885ff4d15f4d5577780722603598`.
- [x] `main` and Tag were pushed without rewriting history.
- [x] GitHub Release exists, is public/non-Draft, and is marked Pre-release.
- [x] Remote Tag target matches the verified local Tag target.

## Known limitations accepted

- Source-only manual deployment; no installer/package/container/service unit.
- Loopback-only supported exposure; no LAN/public deployment contract.
- Digital Asset Trash/Purge and general photo browsing are unavailable.
- External AI Worker is not a separately packaged application in this Release.
- Cross-host deployment remains the explicit post-release acceptance trial.

## Environment note

The first restricted-sandbox attempts could not bind disposable `127.0.0.1` test
servers and therefore produced permission errors before HTTP assertions. The identical
Backend and Web commands were rerun with local loopback permission and passed. No live
catalog database or production asset path was used.

## Decision

Pass. The candidate passed all pre-Tag gates and the public GitHub Pre-release
was independently resolved at
<https://github.com/danielmeng1986/Curator/releases/tag/v0.1.0-internal.1>.
The next acceptance activity is the documented second-host deployment trial.
