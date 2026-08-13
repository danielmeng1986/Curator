# DOC-010 — Restructure UI Design Documentation

## Task ID

`DOC-010` — Status: `Complete`

## Goal

Turn `Docs/UI` into a clearly governed UI design and delivery documentation
set whose current descriptions match the shipped Web client and whose
Specification, feature descriptions, verification evidence, tasks, and
historical audits cannot be confused with one another.

## Scope

- Establish `Docs/UI/README.md` as the directory entry point and authority map.
- Rename and group foundation, data-interaction, feature, verification, and
  historical-audit documents by responsibility.
- Reconcile routes, LAN boundaries, AI Workspace state, Photo ownership,
  Promotion behavior, and readiness evidence with current implementation.
- Update repository links affected by the restructuring.
- Preserve completed UI tasks and the dated audit as implementation history.

## Out of Scope

- Runtime Backend or Web behavior changes.
- User-manual instructions or localization changes.
- Rewriting completed task records to describe work differently from when it
  was performed.

## Inputs and Authority

- `Docs/UI/Specification.md` for UI workflow requirements.
- Current `apps/web/static` routes and accepted browser workflows.
- Backend Authentication, Work Dispatch, AI Workspace, and API contracts.
- `Docs/Documentation-Governance.md` for document lifecycle and authority.
- `Docs/UI/Workflow-Readiness-Matrix.md` and the readiness manifest for current
  verification state.

## Deliverables

- The approved `Docs/UI` directory structure with stable descriptive names.
- Current foundation, interaction, and feature descriptions.
- A verification strategy without duplicating the controlling Specification.
- A clearly marked historical audit and an updated living readiness matrix.
- Updated documentation indexes and links.

## Acceptance Criteria

- Every top-level UI document states its role or is unambiguously classified by
  the UI index.
- No current description calls the shipped AI Workspace or evidence UI a future
  feature, and documented routes match the Web router.
- Default-loopback and explicit trusted-LAN behavior are distinguished.
- Photo CRUD and Album Promotion descriptions match current ownership and
  persistence behavior.
- The dated audit remains historically intact but cannot be mistaken for
  current readiness.
- Repository-local Markdown links resolve after all moves.

## Verification

- Search for retired UI filenames and stale future/readiness wording.
- Check relative Markdown links throughout `Docs`.
- Run relevant documentation consistency checks and `git diff --check`.

## Dependencies

- DOC-001 documentation authority and lifecycle.
- UI-022–029 workflow Specification, remediation, and accepted evidence.

## Risks or Notes

- Completed task files are historical records. Their prose may retain the
  terminology used at execution time, but their links must remain valid.
- File moves should preserve Git history and avoid needless content churn.

## Completion Record

- Replaced the numbered planning layout with the approved UI index,
  foundation, interaction, feature, verification, readiness, audit, and task
  structure.
- Reconciled current hash routes, default-loopback/trusted-LAN behavior, Photo
  ownership, shipped AI Workspace stages, durable Promotion semantics, and the
  13-suite readiness runner with active code and accepted evidence.
- Reduced the former Safety and Acceptance document to a verification strategy;
  normative workflow behavior remains solely in the UI Specification.
- Classified the dated workflow audit as Historical and recorded completion of
  UI-023–028 without rewriting its original findings.
- Updated all repository-local inbound links. Markdown links, user-manual
  parity, schema documentation, readiness-manifest count, and whitespace checks
  pass. No runtime implementation gap was discovered.
