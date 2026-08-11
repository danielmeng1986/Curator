# Curator Web Client Manual

> Supported application: `apps.web` · Last verified: 2026-08-11

<!-- manual-section: purpose -->
## 1. Purpose and boundary

Curator Web is the management Client for Album-level digital assets. It manages
catalog metadata, Imports, operational review, recovery, and AI-assisted naming.
It is not a photo browser or curator application: Album photos have no general
browsing/deletion surface here. Digital Asset Trash is not yet available, and
**Repair Quarantine** is only temporary isolation for repair conflicts.

<!-- manual-section: connect -->
## 2. Open and connect

1. Ask the Server operator for the loopback URL and ensure Backend is running.
2. Open the URL in the browser profile assigned to this device.
3. Open connection settings, enter an **Approved device Token**, then select
   **Validate and connect**.
4. Confirm that the displayed role and navigation match the approved access.

Tokens come from an Administrator after device registration. They are credentials:
do not share them, paste them into reports, or reuse them between people/devices.
**Disconnect** removes the current browser connection; it does not revoke the Token.

<!-- manual-section: navigation -->
## 3. Navigation and shared concepts

Common navigation includes **Dashboard**, **Albums**, **Models**, **Studios**,
**Statuses**, **Operations**, and **Issues**. Write-enabled users also see **Import**.
Admin-only areas include **Repair Quarantine**, **Administrator Center**,
**AI Work Dispatch**, and **AI Review**.

An **Album** is the management unit. **Preview** calculates reviewed impact;
**Execute** applies it. An **Operation** is durable evidence of an attempted change.
An **Issue** records a condition needing review; a **Repair Case** records a proposed
response. AI Workspaces, Dispatch Groups, and Work Items keep assignment, evidence,
review, and Promotion separate from Album status.

<!-- manual-section: roles -->
## 4. Role and capability matrix

| Workflow | Reader | Writer | Administrator |
| --- | --- | --- | --- |
| Browse Albums/entities/Operations/Issues | Yes | Yes | Yes |
| Edit Albums/entities and execute Import | No | Yes | Yes |
| Permitted Issue/Repair decisions | No | Yes | Yes |
| Token administration and recovery operations | No | No | Yes |
| Quarantine, AI Dispatch/review/Promotion | No | No | Yes |

Hidden navigation is not proof of authorization; Backend enforces every request.
See [Reader](reader.md), [Writer](writer.md), or [Administrator](administrator.md).

<!-- manual-section: feedback -->
## 5. Feedback, cancellation, and retry

- A disabled button means prerequisites, selection, acknowledgement, or confirmation
  are incomplete.
- Cancel closes the current review without executing it.
- Validation errors should be corrected in the form; permission errors require an
  Administrator, not repeated submission.
- For an expired, stale, or consumed Preview, return to the source screen and create a
  new Preview. Never reuse its token.
- On uncertain or partial failure, open **Operations** and related **Issues** before
  retrying. The result screen—not button animation—is authoritative.
- Navigation cancels obsolete list refreshes; return to the page to request fresh data.

<!-- manual-section: safety -->
## 6. Safety and troubleshooting

If the Client cannot connect, verify the Backend URL and Token without disclosing it.
If access changed, reconnect with the newly issued Token. A `403` response means the
current role is insufficient. A database Restore deliberately clears the connection.

Always review targets and impact before destructive confirmation. Do not alter the
database or managed files outside supported workflows. Server setup and recovery
boundaries are in the [Backend Server manual](../../server/apps-backend.md).

<!-- manual-section: checklist -->
## 7. Verification checklist

- [ ] The browser is connected to the intended local Backend.
- [ ] The current role and visible navigation are expected.
- [ ] No credential or private path appears in shared material.
- [ ] Previewed target and impact still match before Execute.
- [ ] Completed changes have an Operation/result record.
