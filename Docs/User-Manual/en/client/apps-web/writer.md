# Curator Web Writer Manual

> Required role: Writer (or Administrator) · Last verified: 2026-08-11

<!-- manual-section: purpose -->
## 1. Role purpose and connection

Writer maintains Album-level catalog data and executes reviewed Imports and permitted
Issue/Repair decisions. Connect with an approved Writer Token as described in the
[Client overview](README.md). Writer does not receive recovery or authorization power.

<!-- manual-section: entities -->
## 2. Albums and permanent entities

1. Search/filter **Albums**, open a record, edit permitted metadata/Studio/Model/Album
   relationships, then **Save**.
2. For multiple Albums, select rows, choose **Batch edit selected**, set changes,
   **Review changes**, inspect blocked/affected counts, then **Execute reviewed batch**.
3. Use **Models** and **Studios** to create/edit permitted entities. Deletion can be
   blocked while Albums reference the entity; resolve relationships rather than force it.
4. Treat **Statuses** as governed catalog vocabulary and follow controls shown by the UI.

Album is the asset-management unit. This Client does not expose a general photo browser
or direct photo deletion.

<!-- manual-section: import -->
## 3. Import Albums

1. Open **Import** and select one batch-wide **Import Action**.
2. Add Album source/name entries and choose **Preview**.
3. Review validation, identity, destination, conflicts, and `can_import`; select only
   valid intended entries and choose **Confirm selected**.
4. Recheck the final summary, then choose **Execute reviewed … Import** once.
5. Review **Import Results** and open **View Operation**. Partial failures must be
   investigated before creating a new Preview.

Changing the batch invalidates the old Preview. Never execute a Preview for a different
selection or after its source assumptions changed.

<!-- manual-section: issues -->
## 4. Issues and Repair Cases

Open **Issues**, filter state, and inspect detail/evidence. Choose only an action listed
under `allowed_actions`; the Backend rejects invalid state transitions. In **Repair
Cases**, review proposed filesystem impact before a permitted decision. An approval is
not itself a file operation unless the result says it executed one.

<!-- manual-section: operations -->
## 5. Operation evidence

Use **Operations** filters and pagination to locate the resulting record. Confirm status,
timestamps, actor/type, summary, and linked Issue/Repair evidence. Preserve failed or
partial Operation identity when escalating.

<!-- manual-section: denials -->
## 6. Admin-only boundaries

Writer cannot administer Tokens, bounded suppression, Repair Quarantine, Backups,
Snapshot cleanup, database Restore, AI configuration, Work Dispatch, AI review,
Promotion, Group release, or Workspace closure/archive. Ask an Administrator; do not
attempt direct requests. Digital Asset Trash is not available to any role yet.

<!-- manual-section: checklist -->
## 7. Security, troubleshooting, and checklist

- [ ] The connected device shows Writer or Administrator.
- [ ] Album/entity changes are limited to the intended records.
- [ ] Every batch or Import was freshly previewed and reviewed before Execute.
- [ ] Issues/Repairs used only currently allowed actions.
- [ ] Operation evidence was checked after execution or partial failure.
- [ ] Admin-only work was escalated without sharing the Writer Token.
