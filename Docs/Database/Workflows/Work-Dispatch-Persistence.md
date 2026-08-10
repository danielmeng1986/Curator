# Work Dispatch Persistence

> Documentation status: Current
> Owner: Database
> Last verified: 2026-08-11

## Boundary

Work Dispatch selects eligible Albums and atomically gives each Album to one
active Worker Group. It never changes Album business Status merely to express
assignment. The controlling contract is
[Work Dispatch Workflow](../../Backend/Specifications/Work-Dispatch-Workflow.md).

## Participating data

| Object | Persistence role |
| --- | --- |
| `album` | Scheduling unit and eligibility input |
| `work_dispatch_batch` | One Admin-confirmed selection/execution |
| `work_dispatch_group` | Durable Album assignment history |
| `album_work_reservation` | Active exclusive lock across every Worker kind |
| `work_dispatch_group_item` | Polymorphic link to adapter-owned Work Items |
| `work_dispatch_preview_claim` | Single-use preview-to-Batch binding |
| `work_dispatch_group_closure` | Immutable closure disposition and Operation evidence |
| `operation` | Dispatch/release audit trail |

## Preview and execution

1. Candidate query filters Albums by approved fields and excludes any Album
   having an active `album_work_reservation`.
2. Preview binds candidate identities, filter/order context, Worker kind,
   dataset/schema version, Workspace and model configurations. It writes nothing.
3. Execute claims the preview. In one Service-controlled transaction it creates
   the Batch, one Group and one Reservation per Album, adapter Work Items, and
   Group Item links.
4. `album_id` is the Reservation primary key. A concurrent Dispatch for any
   Worker kind therefore conflicts before two active owners can exist.
5. A conflict or stale candidate fails without a partial Batch/Group/Item set.

## Active work, closure, and release

- Group and Batch are durable identities; Reservation alone represents active ownership.
- Adapter Work Items retain their own execution/review state. Dispatch does not
  flatten those states into Group or Album Status.
- Closure appends `work_dispatch_group_closure` with disposition, reason,
  Operation and summary.
- Release deletes the Reservation and marks the Group released while preserving
  Batch, Group, Item links, closure, adapter results, reviews, and Operations.
- The Album becomes eligible for a later Dispatch only after Reservation removal.
- Redispatch creates new Batch/Group/Item identities; it never reactivates old rows.

## Acceptance evidence

- `test_ai_workspace_workflow_acceptance`
- UI-011F Work Dispatch browser acceptance
- BT-054 through BT-057

