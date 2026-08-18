# UI-036 — Guide Cancelled Work Item Closure

## Task ID

`UI-036` — Status: `Complete`

## Title

Explain Album Reservation and Group Closure After Work Item Cancellation

## Goal

Preserve the existing cancellation and reservation rules while making their
consequences and recovery path clear in Work Dispatch.

## Scope

- Explain before cancellation that cancelling one Failed Work Item preserves
  its Dispatch Group and Album reservation.
- Confirm after cancellation that the Album does not immediately return to
  Available.
- Show contextual Group-detail guidance for remaining Worker work, releasable
  terminal Groups, and whole-Group abandonment.
- Use explicit Group action labels: Release Group, Abandon Group, and Cancel
  Group.

## Out of Scope

- Automatically releasing a Group after its last Work Item is cancelled.
- Changing Work Item, Group, or Album reservation state transitions.
- Making a cancelled Work Item retryable or creating a replacement Work Item.

## Product Contract

1. Cancel Work Item remains item-scoped and preserves the Group.
2. A preserved Group continues to reserve its Album.
3. When remaining Worker and review work is terminal, the Group appears in
   Closure and Release Group returns its Album to Available.
4. Abandon Group is described as an exceptional whole-Group closure, not as
   the normal continuation of Work Item cancellation.
5. The UI never implies that cancellation alone makes an Album dispatchable.

## Acceptance Criteria

- The cancellation confirmation describes the retained reservation and Release
  Group path.
- A mixed Cancelled/Pending Group explains that other Worker runs remain.
- A fully terminal Group explains that Release Group frees the reservation.
- Group buttons communicate their scope without relying on surrounding context.
- UI contract and real-browser Work Dispatch acceptance pass.

## Completion Record

- Added reservation-aware cancellation feedback and contextual next-step
  guidance to Dispatch Group detail on 2026-08-18.
- Clarified all Group action labels without changing Backend behavior.
