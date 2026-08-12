# DOC-009 — Refresh UI Device Enrollment Manuals

## Task ID

`DOC-009` — Status: `Complete`

## Title

Refresh Bilingual Manuals for UI-Only Device Enrollment

## Related Specification(s)

- [User Manual Specification](../User-Manual/Specification.md), shared access-and-registration workflow and multilingual contract.
- [Authentication](../Backend/Specifications/Authentication.md), managed proof and device enrollment lifecycle.

## Goal

Replace terminal-first Reader/Writer enrollment instructions with the completed Admin/requester UI workflow in both mandatory locales while retaining an explicitly labeled operator fallback if still supported.

## Scope

- Update English and Simplified Chinese Backend, Web overview, access/registration, Administrator, Reader, and Writer manuals.
- Document one-time Registration Proof display, browser-local candidate Token handling, approval states, rotation/disablement, and recovery.
- Update the manual verification gate for new UI labels, links, and required sections.

## Out of Scope

- Implementing Backend or Web behavior.
- Documenting behavior before browser acceptance proves it.

## Implementation Steps

1. Reconcile the accepted UI labels, states, credential boundaries, and operator fallback with the User Manual Specification.
2. Update the mirrored English and Simplified Chinese access, role, overview, and Backend manuals.
3. Extend the manual gate where required and verify commands, headings, links, redaction, and locale parity.

## Acceptance Criteria

- A normal Reader/Writer enrollment happy path contains no terminal, developer-console, JSON, or `curl` requirement.
- Admin and requester steps clearly distinguish Registration Proof, Device Token, Bootstrap Code, and browser device identity.
- English and Chinese files have matching structure, commands, warnings, and link targets.
- Any retained CLI/environment fallback is labeled as operator/automation fallback rather than the normal user workflow.
- Documentation contains no real credential, private identity, or production path.

## Dependencies

- `UI-021` — the complete browser workflow must be accepted before manuals describe it as supported.

## Verification

- Run `python3 tools/check_user_manuals.py` twice after the final edits.
- Verify all documented UI labels and paths against the accepted browser workflow.

## Risks or Notes

- Do not remove emergency/operator fallback instructions until Backend compatibility policy is finalized.

## Completion Record

- Added mirrored English/Chinese shared access-and-registration manuals and linked every Web role/overview to the UI-only workflow.
- Extended the manual parity gate; no normal Reader/Writer enrollment step requires terminal, developer tools, UUID copying, JSON, or `curl`.
