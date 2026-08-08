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

## Stable review direction

The exact state names and transitions remain a UI-011B Specification decision.
The stable review surface is expected to include submission, reviewer, decision,
decision time, review notes, concurrency version, Promotion result, and latest
Operation identity. Approval and Promotion are not assumed to be the same step.

AI suggestions are always visibly distinct from human revisions and final
accepted values. No suggestion is accepted automatically, and no permanent
Album is created until the approved Backend workflow permits it.

## Readiness

The new Workspace is `Blocked by Specification` until UI-011A/B are approved,
and then remains `Not Implemented` until its Backend APIs, UI-011C, and browser
acceptance UI-011D are complete.
