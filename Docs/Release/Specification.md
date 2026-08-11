# Curator Release Specification

> Documentation status: Approved  
> Owner: Release engineering  
> Last verified: 2026-08-12

## Purpose

This Specification defines repeatable Curator milestones, Tags, and Releases.
It distinguishes an internal deployment baseline from a public, supported
distribution and requires every published version to carry reproducible scope,
safety, migration, documentation, and acceptance evidence.

## Release classes

| Class | Version form | GitHub status | Intended use |
| --- | --- | --- | --- |
| Internal deployment | `vX.Y.Z-internal.N` | Pre-release | Owner-controlled deployment and recovery testing on another host |
| Alpha | `vX.Y.Z-alpha.N` | Pre-release | Broader feature evaluation after portability boundaries are documented |
| Beta | `vX.Y.Z-beta.N` | Pre-release | Installation/upgrade candidate with declared supported environments |
| Stable | `vX.Y.Z` | Release | Supported distribution meeting published compatibility and upgrade policy |

The release class is a promise boundary. An internal release must not be
described as generally installable merely because GitHub provides source archives.

## Version and Tag rules

- Versions follow Semantic Versioning prerelease syntax; the Git Tag is exactly
  the version, for example `v0.1.0-internal.1`.
- Every release Tag is annotated and points to a clean, reviewed release commit.
- A published Tag is immutable. Corrections use a new prerelease sequence or patch
  version; a Tag must never be moved to different content.
- Release notes identify the exact commit, previous baseline, release class, date,
  supported applications, schema/migration boundary, and known limitations.
- Tags and Releases contain no database, backup, Token, model binary, private asset,
  machine-local configuration, `var/` runtime state, or dependency cache.

## Required release contents

Each release record under `Docs/Release/<version>/` contains:

1. `Release-Notes.md` — purpose, included capabilities, changes, and limitations;
2. `Deployment-Guide.md` — prerequisites, clean-host deployment, configuration,
   migration, first Admin, verification, upgrade, rollback, and secret boundaries;
3. `Verification-Record.md` — candidate commit, environment, commands/results,
   documentation refresh, repository cleanliness, and approval.

GitHub may provide automatic source archives. Additional artifacts are optional and
must be reproducibly built, checksummed, and free of local/runtime data. A source-only
internal release must state that no installer or binary package is supplied.

## Release task lifecycle

Release work uses `REL-*` tasks in `Docs/Release/Tasks/`:

1. **Proposed** — define version, class, scope, dependencies, and acceptance criteria.
2. **In Progress** — freeze scope; prepare notes, deployment guide, and verification record.
3. **Candidate verified** — run all required gates against the exact candidate worktree.
4. **Committed** — commit release records; record the resulting candidate commit.
5. **Tagged** — create and locally verify the annotated immutable Tag.
6. **Published** — push the commit and Tag, then create the matching GitHub Release.
7. **Complete** — verify the remote Tag/Release and update the task with final evidence.

A task may stop at Tagged when no publication target is authorized. Failed verification
returns the task to In Progress; it never permits publishing with missing evidence.

## Required verification gates

Before tagging an internal deployment release:

- the worktree is clean and the candidate is based on the intended branch;
- complete Backend regression passes in disposable databases/resources;
- Web contract, UI readiness, and default Playwright acceptance pass;
- schema documentation and bilingual user-manual gates pass twice where required;
- supported application entry points and migration/bootstrap commands are verified;
- the User Manual Release Refresh Record is completed for the candidate;
- release documents contain no secret, production data, or private machine path;
- known blocked features and portability limitations are explicit.

Stable releases require additional supported-platform, upgrade-from-supported-version,
rollback, package integrity, and public installation acceptance that internal releases
do not claim.

## Deployment and rollback boundary

Deployment always creates local configuration and runtime directories outside versioned
source. An existing database is backed up and the Backend stopped before migration.
Rollback means stop the new Backend, preserve failure evidence, restore a verified
pre-upgrade recovery point using the documented protected process, and return to the
previous immutable Tag. Direct SQL and ad-hoc live database replacement are forbidden.

## Publication policy

- GitHub internal Releases are marked **Pre-release**.
- Release title and notes repeat the internal/non-public support boundary.
- Publication occurs only after the release commit and annotated Tag exist locally.
- After publication, compare local and remote Tag targets and open the Release record.
- A deployment test on another host is recorded as follow-up evidence; discovered gaps
  become REL, BT, UI, MT, DOC, or DBDOC tasks in the owning area.

## First release decision

The first governed release is:

`v0.1.0-internal.1 — Backend and Web Administration Baseline`

It is intended for the project owner to reproduce deployment on another controlled
host. It is source-only and does not claim a public installer, remote/LAN exposure,
third-party support, or a completed standalone AI Worker distribution.
