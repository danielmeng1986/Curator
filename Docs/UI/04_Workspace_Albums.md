# AI Collection Workspace

## Historical boundary

The historical `workspace_album` collection is closed and archived by MT-008.
It has no active Web UI route, navigation item, edit action, batch action, or
promotion journey. Existing Backend handlers retained for compatibility or
historical verification do not make that collection a supported UI surface.

Historical records remain available only through approved audit, migration, or
recovery evidence. They must never be loaded as active fixtures or input for a
new AI Workspace workflow.

## Future Workspace contract

Curator will require a new dataset-aware Workspace for AI Worker collection and
human review. UI-011A must define the product/data contract and UI-011B must
define the stable review state machine and read model before routes or pages are
implemented.

The future contract must keep these concerns distinct:

- dataset identity, schema version, source provenance, and AI-owned results;
- human-editable review values and explicit approval/rejection evidence;
- system-managed state, version, timestamps, Operations, Issues, and permanent
  entity links; and
- dataset adapters for variable fields without duplicating state-transition or
  Promotion policy in the client.

## Album work dispatch entry

The active AI Workspace begins with an Admin dispatch console, not by copying
all `TEMPORARY` Albums or reopening historical `workspace_album`. An Admin may
filter the permanent Album catalogue by supported Album fields and choose a
bounded set for one Worker kind and Workspace.

The default Available view contains only Albums for which the Backend reports
no active Album Work Reservation. A successful dispatch moves the Album from
Available to Active work and exposes its Batch, Group, Work Items, Workspace,
and Operation links. History remains visible after release.

One Album may have only one active Dispatch Group across every Worker kind,
even when different Workers would edit different fields. Multiple model
configurations used for one comparison appear as Work Items inside that single
Group. Dispatch never changes `album.status_id`; Album business Status, Worker
run state, and human review state are displayed as separate concepts.

## Stable review contract

The stable state machine is `ReadyForReview → InReview → Approved | Rejected |
ReworkRequested`. Approval and Promotion are separate. Approval freezes one AI
recommendation or a validated human revision; rating is optional from 1–5, and
Reject/Rework require a reason. Rework creates a new linked Work Item in the
same Dispatch Group and preserves all prior output and decision evidence.

AI suggestions are always visibly distinct from human revisions and final
accepted values. No suggestion is accepted automatically, and no permanent
Album is created until the approved Backend workflow permits it.

## Readiness

UI-011A/B are approved. The Backend implementation proceeds through BT-050/051;
the visible review UI and browser acceptance remain UI-011C/D work.
