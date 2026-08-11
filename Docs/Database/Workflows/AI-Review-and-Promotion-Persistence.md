# AI Review and Promotion Persistence

> Documentation status: Current
> Owner: Database
> Last verified: 2026-08-11

## Boundary

The AI Worker reads only Manifest-bound Photo evidence through REST, submits a
Vision result followed by a Writer result, and cannot promote Album data.
An Admin reviews results and explicitly promotes one Album name. Controlling
contracts are the AI Workspace tasks/specifications, Work Dispatch Workflow,
and [AI Workspace Acceptance Fixture](../../Backend/Specifications/AI-Workspace-Acceptance-Fixture.md).

## Participating data

| Object | Persistence role |
| --- | --- |
| Dataset/Workspace/configuration tables | Versioned contract and execution input |
| Work Item and attempt tables | Current execution projection plus attempt history |
| Manifest and evidence Photo tables | Immutable Backend-selected evidence identity |
| result state/stage tables | Current stage projection plus immutable Vision/Writer payloads |
| review, decision, rework tables | Current human review plus immutable decisions/lineage |
| Promotion and claim tables | Reviewed single-use Album mutation outcome |
| Workspace retention and Group closure | Final lifecycle/audit evidence |

## Dispatch, execution, and evidence

1. Dispatch creates one Work Item per chosen model configuration and stores a
   configuration snapshot. Several configurations may analyze the same Album
   inside one Group.
2. Claim creates an attempt and lease. Wrong Worker, expired lease, or stale
   attempt cannot submit successful state for another claim.
3. Backend discovers eligible image files under canonical Album path, applies
   configured sample count and selection rules, and writes one immutable Manifest
   plus ordered evidence rows. Insufficient/no usable images produce a reported failure.
4. Evidence transfer validates Manifest, Work Item, actor, relative path, size,
   modification time and hash; arbitrary Album filesystem browsing is not exposed.
5. Vision result is validated and appended first. Writer result must bind the
   same Manifest and configuration snapshot. Result state advances only after
   the corresponding immutable stage is stored.

## Review, rework, and Promotion

1. Ready result materializes/updates `ai_work_item_review` as the current review projection.
2. Every transition appends `ai_work_item_review_decision` with evidence,
   reviewer, Operation and time. Rating/notes evaluate the Work Item result.
3. Approval selects exactly one recommended name or a constrained human revision.
4. ReworkRequested creates a new Work Item in the same Group, inherits the
   model configuration, and records old→successor lineage in `ai_work_item_rework`.
5. Promotion preview is zero-write and binds Workspace, approved Work Item,
   Album, selected name, version and current Album state.
6. Confirmed Promotion claims the preview, takes a risk-required Snapshot,
   updates Album title/status as specified, and appends an immutable Promotion outcome.
7. Partial unique indexes permit many model results but only one successful
   winner for the Workspace+Album and winning Work Item.

## Closure and retention

- Rejected, reworked, failed and non-winning results remain retained.
- Group release removes only active Reservation; all AI evidence remains.
- Workspace closure records outcome/reason/actor/Operation in retention state;
  archive preserves the dataset, configuration snapshot, evidence, results,
  decisions, Promotion and Operations indefinitely for audit.
- Archived Workspace mutation and duplicate Promotion are rejected without Album change.

## Acceptance evidence

- `test_ai_workspace_workflow_acceptance`
- UI-011D Workspace review browser acceptance
- BT-043 through BT-053, BT-057, and BT-058
