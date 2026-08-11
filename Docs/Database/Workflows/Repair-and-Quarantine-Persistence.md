# Repair and Quarantine Persistence

> Documentation status: Current
> Owner: Database
> Last verified: 2026-08-11

## Boundary

Repair reconciles expected database/filesystem state. Repair Quarantine safely
isolates filesystem items involved in that operational workflow. It is not the
future Digital Asset Trash lifecycle. Controlling contracts are
[Repair Workflow](../../Backend/Specifications/Repair-Workflow.md),
[Issue Management](../../Backend/Specifications/Issue-Management.md), and the
Snapshot Specification.

## Participating data

| Object | Persistence role |
| --- | --- |
| `operation` | Parent/related action trail and recovery context |
| `issue`, `issue_link` | Review queue, decision state, and polymorphic evidence links |
| `repair_case` | Current Repair classification, state, confirmation, and verification |
| `repair_suppression` | Bounded Admin suppression policy with expiry/revocation |
| `quarantine_item` | Original/quarantine location, inventory, hold/expiry and Restore evidence |
| preview claim tables | Single-use Quarantine, Snapshot cleanup, or database Restore execution |
| Snapshot/quarantine directories | Backend-controlled recovery artifacts |

## Repair sequence

1. A failed or inconsistent Operation creates/links an Issue and Repair case.
2. Classification selects Automatic, Assisted, or Manual policy. Only a
   canonicalization-only rename with authoritative evidence is automatic.
3. Review actions update the current Issue/Repair projection and append linked
   Operations. Stale, unauthorized, or invalid transitions preserve prior state.
4. Assisted action requires the exact confirmation contract. Verification must
   pass before the Repair is resolved; failure remains unresolved and auditable.
5. Admin suppression stores a narrow fingerprint/scope with expiry. It does not
   delete Issue history and does not authorize unsafe filesystem mutation.

## Quarantine and Restore sequence

1. Preview inventories the exact item and required Snapshot/recovery evidence
   without moving it.
2. Confirmed Admin execution claims the preview, creates an Operation, and moves
   the item to a Backend-controlled quarantine path.
3. `quarantine_item` retains original path, inventory, reason, hold/expiry, and
   Operation evidence. Cancellation or rejected preview creates no move.
4. Restore is separately reviewed and claimed. It never overwrites an occupied
   destination and records restore time, destination, and Operation only after
   verified success.
5. Replay, collision, missing item, or verification failure preserves truthful
   current filesystem and durable state.

## Retention and separation

- Issue, Repair, suppression, Quarantine, Restore, and Operation history remain traceable.
- A released or restored item is not treated as if the original action never happened.
- Database Restore preview claims and Snapshot cleanup claims are separate from
  item Quarantine claims even though all use reviewed single-use execution.
- Permanent Digital Asset purge requires BT-033–035 and UI-010E; this workflow
  cannot be reused to bypass those blocked safety decisions.

## Acceptance evidence

- `test_repair_policy_workflow_acceptance`
- `test_repair_decision_workflow_acceptance`
- `test_quarantine_workflow_acceptance`
- UI-014 and UI-015 browser acceptance
