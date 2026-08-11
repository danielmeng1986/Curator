# DOC-005 — Establish Application User Manual Specification

## Task ID

`DOC-005` — Status: `Complete`

## Goal

Establish the authoritative structure, scope, localization, role, safety, and
release-maintenance contract for Curator application user manuals.

## Scope

- Classify supported `apps/` applications as Server or Client.
- Define fixed Server/Client and role-manual structures.
- Require English and Simplified Chinese mirrored delivery.
- Define tools exclusion and strong-application-association exceptions.
- Define milestone/Tag refresh triggers and verification gates.

## Deliverables

- `Docs/User-Manual/Specification.md`.
- `Docs/User-Manual/README.md` and canonical locale layout.
- Follow-up authoring and maintenance tasks.

## Acceptance Criteria

- Current apps.backend/apps.web boundaries and roles are covered.
- Admin first authentication, approvals, Issues, authorization, high-risk and
  AI review workflows are mandatory manual content.
- A one-locale or unverified release cannot be called complete.
- Tools do not become a general manual surface.

## Verification

- Compare included apps with supported runnable `apps/` entry points.
- Cross-check roles and high-risk workflows with UI/Backend Specifications.
- Verify all Specification/index links.

## Dependencies

- DOC-001 through DOC-004.

## Completion Record

- Added the approved manual Specification and delivery index.
- Classified apps.backend as Server and apps.web as Client.
- Defined bilingual mirror, role content, safety, exception, and recurring release rules.

