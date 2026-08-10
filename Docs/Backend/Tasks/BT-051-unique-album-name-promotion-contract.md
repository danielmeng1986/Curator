# BT-051 — Implement Unique Album Name Promotion Contract

## Task ID

`BT-051` — Status: `Complete`

## Title

Promote Exactly One Approved AI Name to an Existing Album

## Related Specification(s)

- UI-011A AI Collection Workspace Specification, Album-name outcome.
- UI-011B Approval/Promotion separation.
- [Snapshot Specification](../Specifications/Snapshot-Specification.md).
- [Operation Logging](../Specifications/Operation-Logging.md).

## Goal

Atomically promote one approved AI Workspace selection to the existing
Album name while preventing competing model runs from producing multiple winners.

## Scope

- Promotion preview bound to Work Item/version, approved selected name,
  Album identity/current name/version, Workspace, and database state.
- Signed expiring single-use execution, validation, exact Admin confirmation,
  unique `workspace_album_name_promotion` winner evidence, and idempotent retry.
- Atomic Album-title update, prior/new value retention, Operation, snapshot risk,
  Issue/failure context, calculated Album Status consequence, and
  `Promoted`/`PromotionFailed` outcome.
- Dataset policy maps source Status `TEMPORARY` to `NAME_GENERATED` on success;
  every other source Status is retained in the first implementation. Clients
  cannot nominate a target Status.

## Out of Scope

- Creating a new Album, modifying filesystem paths, or promoting analysis prose.
- Superseding a prior successful winner in the first implementation.

## Dependencies

- BT-050 approved selection and BT-032 Album mutation/relationship safety.
- Approved rule: within one AI Workspace an Album has at most one successful winner.

## Implementation Steps

1. Add promotion evidence schema and database uniqueness constraint.
2. Implement preview, validation, snapshot/Operation, and atomic execution service/API.
3. Add competing-model, replay, stale Album, duplicate, failure, and idempotency tests.

## Acceptance Criteria

- Only an Approved Item with a frozen selected name is promotable.
- Competing approved runs for the same Album cannot both succeed in one Workspace.
- Reject, Rework, preview, cancellation, stale, and failed execution do not change Album title.
- Success updates exactly one Album, applies the specified Status policy in the
  same transaction, persists the winner and Operation, and is idempotent.
- Preview discloses the current name/Status and calculated resulting name/Status;
  reject, failure, or stale execution changes neither field.

## Verification

- Atomic race/uniqueness tests, API lifecycle tests, snapshot failure injection,
  and complete Backend regression.

## Risks or Notes

- A future rename from another Workspace requires an explicit supersede/history
  policy; it must not be inferred by this task.
- Promotion does not itself release the Album Work Reservation; BT-057 closes
  the Group after all terminal obligations are satisfied.

## Completion Record

- Added successful/failed Promotion evidence and partial unique constraints for
  one successful Workspace/Album and Work Item winner.
- Added signed, expiring, Admin-bound preview and exact-name confirmation with
  Album, review, selected-name, Workspace, and Status stale checks.
- Successful execution atomically updates Album title, maps only `TEMPORARY` to
  `NAME_GENERATED`, retains every other Status, and records the Operation.
- Exact replay is idempotent; competing winners, stale state, snapshot failure,
  and injected database failure cannot mutate Album. Database failure retains
  `PromotionFailed` evidence and a failed Operation.
