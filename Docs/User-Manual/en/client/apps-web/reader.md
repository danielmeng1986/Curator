# Curator Web Reader Manual

> Required role: Reader (or higher) · Last verified: 2026-08-11

<!-- manual-section: purpose -->
## 1. Role purpose and prerequisites

Reader is for catalog and operational review without mutation. Obtain an approved
Reader Token for this device and read the [Client overview](README.md) first.
For a new browser, use the UI-only [Access and Device Registration](access-and-registration.md) workflow.

<!-- manual-section: login -->
## 2. First connection

Enter the **Approved device Token** in connection settings and choose **Validate and
connect**. Confirm the role is Reader. If the Token is pending, expired, or revoked,
ask an Administrator to review the device; do not borrow another Token.

<!-- manual-section: workflows -->
## 3. Permitted workflows

1. Use **Dashboard** for catalog/health summaries exposed to the role.
2. Use **Albums** to search, filter by date/metadata, page through results, and open
   Album metadata. Photo-library browsing is intentionally absent.
3. Use **Models**, **Studios**, and **Statuses** to inspect permanent entities and
   their Album summaries.
4. Use **Operations** to filter/page history and open available evidence.
5. Use **Issues** and **Repair Cases** to inspect state and review context.

<!-- manual-section: denials -->
## 4. Expected denials and escalation

Reader cannot save entities, batch edit, Import, decide Issues/Repairs, or access Admin
workflows. Write/Admin navigation is hidden and direct requests return insufficient
scope. Request the least additional role from an Administrator with the work reason.

<!-- manual-section: security -->
## 5. Review and disclosure boundaries

Reader has no execution confirmations. Some sensitive recovery, filesystem, credential,
and AI administration context is intentionally withheld. Do not infer or request raw
paths/secrets merely because a summary omits them.

<!-- manual-section: troubleshooting -->
## 6. Troubleshooting and checklist

- [ ] Connection identifies the intended Reader device.
- [ ] Browse pages load but mutation/Admin controls remain unavailable.
- [ ] Filters can be cleared and pages navigated without changing data.
- [ ] A denied action is escalated instead of retried with another person's Token.

For Server availability, contact the operator using the
[Backend Server manual](../../server/apps-backend.md).
