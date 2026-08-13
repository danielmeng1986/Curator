# DOC-011 — Add AI Worker Deployment Manual

## Task ID

`DOC-011` — Status: `Complete`

## Goal

Add a bilingual operator manual for deploying and verifying Curator AI Worker
on a Windows 11 host inside WSL2 Ubuntu 24.04, while reusing the existing
Writer registration concepts.

## Scope

- Add mirrored English and Simplified Chinese AI Worker manuals.
- Cover WSL2/Ubuntu preparation, repository placement, Backend trusted-LAN
  exposure, connectivity, Writer access, secrets, model/runtime placement,
  verification, update, and troubleshooting boundaries.
- Register the Worker manual in the User Manual Specification, index, and
  automated bilingual/parity gate.
- Coordinate with MT-009 for the production Worker entry point and service loop.

## Out of Scope

- Selecting a production model or GPU backend for every Worker host.
- Repeating the complete browser device-enrollment workflow.

## Inputs and Authority

- `workers/ai_worker` current implementation and tests.
- Backend Authentication, API, and Work Dispatch Specifications.
- Microsoft WSL installation and networking documentation.
- Existing bilingual access-and-registration manual.

## Deliverables

- `Docs/User-Manual/en/worker/ai-worker.md`.
- `Docs/User-Manual/zh-CN/worker/ai-worker.md`.
- Updated manual index, Specification, and release gate.
- MT-009 runnable Worker implementation and operating commands.

## Acceptance Criteria

- Both locales have identical structure, commands, warnings, and link targets.
- The manual publishes only the startup and enrollment commands implemented by
  MT-009.
- The reader can deploy on WSL2 Ubuntu 24.04, verify Backend reachability, and
  obtain least-privilege Writer access without learning raw API registration.
- Token, model, database, filesystem, and LAN boundaries are explicit.
- The automated user-manual gate includes the Worker manual.

## Verification

- Run `python3 tools/check_user_manuals.py` twice.
- Run Worker unit tests and Markdown link checks.

## Dependencies

- DOC-005 application user-manual structure.
- DOC-009 UI-only Reader/Writer enrollment instructions.
- MT-009 supplies the runnable deployment boundary.

## Risks or Notes

- WSL networking evolves independently of Curator. The manual links to current
  Microsoft guidance and avoids treating mirrored mode as mandatory.

## Completion Record

- Added mirrored English and Simplified Chinese Worker manuals for Windows 11
  with WSL2 Ubuntu 24.04 preparation, trusted-LAN connectivity, Writer identity,
  secrets, evidence, model, lifecycle, troubleshooting, and safety boundaries.
- Documented that browser-owned enrollment cannot provision a headless Worker
  Token; MT-009 supplied the documented runnable service entry.
- Created and completed MT-009 for headless enrollment, configuration,
  polling/heartbeat, inference, cleanup, graceful shutdown, and end-to-end
  acceptance.
- Extended the manual Specification and parity gate. Both gate runs, Worker
  unit tests, Markdown links, and whitespace checks pass.
