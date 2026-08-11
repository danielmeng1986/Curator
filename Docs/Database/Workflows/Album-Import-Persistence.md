# Album Import Persistence

> Documentation status: Current
> Owner: Database
> Last verified: 2026-08-11

## Boundary

The Backend previews and executes Album Import. The client never writes catalog
tables or moves files directly. The controlling behavior is the
[Import Workflow](../../Backend/Specifications/Import-Workflow.md); this page
only maps that behavior to persistence.

## Participating data

| Object | Persistence role |
| --- | --- |
| `studio`, `model`, `album`, `album_model` | Permanent catalog outcome |
| `import_preview_claim` | Single-use reviewed-preview execution claim |
| `operation` | Durable Import status, summary, errors, links, and recovery context |
| `issue`, `repair_case` | Durable follow-up when database/filesystem outcome needs review |
| Snapshot file | Filesystem recovery point for risk-qualified execution |

## Sequence

1. Preview reads catalog/path state and computes COPY, MOVE, or DATABASE_ONLY.
   It writes no business row, Operation, Snapshot, or file.
2. The signed preview identity binds normalized input, chosen action, and source
   evidence. Cancellation ends here with no write.
3. Execute atomically claims `preview_uuid` in `import_preview_claim`. A duplicate,
   expired, changed-source, or mismatched preview is rejected before business mutation.
4. Execution creates an `operation` and applies catalog changes through the
   Import Service/Repository transaction.
5. COPY/MOVE filesystem work is verified against the intended canonical path;
   DATABASE_ONLY deliberately performs no filesystem mutation.
6. Success completes the Operation and returns the permanent Album identity.
   A partial filesystem failure records truthful `NeedsRepair` evidence and
   creates/links Issue or Repair state instead of claiming full success.

## Retention and failure truth

- A successful claim remains durable to prevent replay.
- Cancelled preview has no claim or business outcome.
- Catalog transaction failure rolls back catalog writes; filesystem truth is
  inspected and reported independently.
- Operation history and Repair/Issue links remain after resolution.
- Source directories are preserved for COPY, removed only after verified MOVE,
  and untouched for DATABASE_ONLY.

## Acceptance evidence

- `test_import_workflow_acceptance`
- UI-013 full Import browser acceptance
- BT-019, BT-020, BT-026, BT-027, and BT-036
