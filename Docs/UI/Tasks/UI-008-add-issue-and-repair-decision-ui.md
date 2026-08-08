# UI-008 — Add Issue and Repair Decision UI

## Task ID

`UI-008` — Status: `Proposed`

## Title

Add Issue Review and Repair Decision UI

## Related Specification(s)

- [Issue Management](../../Backend/Specifications/Issue-Management.md).
- [Repair Workflow](../../Backend/Specifications/Repair-Workflow.md).

## Goal

Allow authorized users to review Issues and execute only Backend-approved
Repair decisions with explicit evidence, confirmation, and traceability.

## Scope

- Issue queues, status/ownership filters, detail, links, and allowed transitions.
- Repair classification, proposed action/reason/evidence, accept, reject, suppression, manual confirmation, and verified outcome.
- Role-aware ownership and administrative actions.

## Out of Scope

- Client-side repair classification or arbitrary filesystem commands.
- Quarantine item management, handled by UI-009.

## Dependencies

- UI-002, UI-003, and UI-007.
- Supported Issue/Repair `/api/v1` read and decision contracts; missing endpoints require separately scoped Backend tasks.

## Implementation Steps

1. Inventory required read/decision APIs and create Backend tasks for readiness gaps.
2. Build Issue list/detail and policy-driven Repair decision views.
3. Add tests for every allowed and rejected decision/state transition.

## Acceptance Criteria

- The UI displays Backend classification and permitted actions without inferring policy.
- Assisted/manual actions require the specified confirmation; unsafe automatic rename cannot be forced through UI payload changes.
- Reject, suppression, ownership, and resolution obey role rules and write truthful Operations.
- Invalid, stale, or repeated decisions are rejected with zero unintended filesystem/business mutation.

## Verification

- Run Backend repair-policy, decision, and traceability workflow acceptance.
- UI-014 supplies complete browser evidence.

## Risks or Notes

- Current Backend Service readiness does not imply that every required UI endpoint/read model already exists.

