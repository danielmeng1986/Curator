# Curator Web Administrator Manual

> Required role: Administrator · Last verified: 2026-08-11

<!-- manual-section: purpose -->
## 1. Role purpose and prerequisites

Administrator adds authentication, recovery, Quarantine, and AI workflow authority to
Writer capabilities. Read the [Writer manual](writer.md) and ensure Backend backup
health is understood. Use a dedicated Admin device/profile and protect its Token.

<!-- manual-section: bootstrap -->
## 2. Initialize the first Administrator

1. On the Backend host, start the Server and open its `127.0.0.1` URL.
2. In a local terminal run:

   ```bash
   python3 -m apps.backend auth create-bootstrap-code
   ```

3. Select **Initialize administrator**, enter the ten-minute single-use Code and an
   Administrator device name, then initialize.
4. Copy the Admin Token shown once into approved secure storage. Check **I have stored
   the Token securely**, continue, and verify **Administrator Center**.

The terminal boundary proves local control. It is not a recovery shortcut after an Admin
exists. Full Server instructions are in the [Backend manual](../../server/apps-backend.md).

<!-- manual-section: authentication -->
## 3. Devices and Tokens

Generate/rotate/disable Registration Proof and approve UI-only Reader/Writer enrollment as described in [Access and Device Registration](access-and-registration.md).

In **Administrator Center → Devices and Tokens**:

1. Verify a pending registration's device identity and requested role/scopes.
2. Approve only least privilege, or reject it. A newly issued Token is shown once;
   transfer it securely and close the result only after storage is acknowledged.
3. Review renewal requests before approval; the replacement Token is also shown once.
4. Before **Revoke**, review the device/Token and enter the required high-risk
   confirmation. Revocation immediately removes access.

Stored Token plaintext and hashes are never displayed. Backend protects the final usable
Admin Token; never treat that protection as a substitute for a second recovery plan.

<!-- manual-section: issue-admin -->
## 4. Issue, Repair, suppression, and Quarantine

Review Issue and Repair evidence and use only currently allowed decisions. Create a
bounded suppression only for the displayed candidate scope and documented reason.

For an approved repair conflict, choose **Review Quarantine move**, inspect original and
isolated destinations, then **Execute reviewed Quarantine**. Quarantine does not resolve
the Issue. To return an isolated item, open **Repair Quarantine**, select it, choose
**Review restore to original path**, inspect conflicts, and execute the fresh Preview.
It is not Digital Asset Trash, which remains unavailable.

<!-- manual-section: backup -->
## 5. Backups, Snapshots, and database Restore

Use **Backups and Snapshots** to inspect catalogued recovery points, create an
Administrator Snapshot, and verify it before reliance. Snapshot cleanup requires a
fresh Preview and high-risk confirmation; preserve required recovery points.

Database Restore replaces the active catalog:

1. Establish a write-free maintenance window and open **Database Restore**.
2. Select only a verified recovery point and choose **Review Restore**.
3. Read preflight impact and protected pre-Restore Snapshot behavior; type the exact
   confirmation phrase, then select **Restore reviewed database** once.
4. Wait for post-Restore integrity verification. On success, cached Admin data and the
   connection are cleared; reconnect with a Token valid in the restored database.
5. On failure, stop and preserve Operation/log/recovery evidence. Do not retry blindly
   or replace database files manually.

<!-- manual-section: ai-config -->
## 6. AI configuration, Workspace, and Dispatch

In **Administrator Center → AI Model Configurations**, create/version the llama.cpp model
and sampling parameters, including requested sample count. Disable obsolete
configurations rather than rewriting historical evidence.

Create/select an AI Workspace, then open **AI Work Dispatch**:

1. Filter the available Album pool, select explicit Albums (or a bounded filtered count),
   Worker, Workspace, and one or more enabled model configurations.
2. Preview and verify Album/Group/Work Item counts and exclusivity conflicts.
3. Acknowledge the reviewed impact and choose **Dispatch reviewed Albums**.

Dispatch does not change Album Status. An active dispatch key prevents the same Album
from being concurrently assigned to another Worker; release/closure restores eligibility.

<!-- manual-section: ai-review -->
## 7. AI review, rework, Promotion, and closure

Open **AI Review**, filter the queue, and inspect a Work Item. Review the analysis JSON,
recommended names, model configuration, and exact sampled photo evidence before deciding.

- **Approve** accepts the result for subsequent use; it does not itself rename the Album.
- **Request rework** creates a new Work Item in the same Dispatch Group, inherits the
  model configuration, and links the old item as evidence.
- **Reject** records that the result must not be promoted.
- Administrator evaluation applies to that Work Item result, not globally to the model.

Promotion is separate: choose exactly one approved candidate or a valid human-edited
name for an Album, preview it, and execute once. Only one promoted `album_name` can win,
even when several model configurations analyzed the Album. Review Operation/Issue output.
Human Review fields are saved as a browser-profile draft. Refresh or restart
restores a compatible draft. If the Backend review version changed, Curator
requires **Keep text and rebase** or **Discard local draft** before submission.
Release completed Groups, then close/archive a Workspace only after its active work and
retention requirements permit it. Do not purge audit evidence to tidy the queue.

<!-- manual-section: risk -->
## 8. High-risk behavior and expected denials

Typed confirmation, acknowledgements, fresh Preview tokens, current versions, and final-
Admin checks are safety controls. Never bypass them. A `400` means input/transition needs
correction; `409` means current state conflicts or became stale; refresh and reassess.
Reader/Writer denial is expected for every section in this manual.

<!-- manual-section: checklist -->
## 9. Verification checklist

- [ ] Admin Token is stored securely and never disclosed in screenshots/logs.
- [ ] Grants use least privilege and final-Admin safety remains intact.
- [ ] Every destructive/recovery action uses a fresh Preview and exact confirmation.
- [ ] Restore has verified pre/post evidence and reconnect behavior is understood.
- [ ] AI decisions cite model configuration and sampled photo evidence.
- [ ] Promotion selects one name; rework preserves the old Work Item.
- [ ] Operations and Issues confirm durable outcome, including partial failure.
