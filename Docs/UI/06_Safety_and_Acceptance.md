# Safety and Acceptance

## Validation, Safety, and Audit

The UI follows Curator’s reviewable, traceable, and reversible workflow principles.

- Validate required values, dates, numeric values, duplicate relationships, foreign-key existence, and path conflicts before enabling Save or Import.
- Use inline field validation plus a page-level summary for blocked operations.
- Preview every multi-record change and import; do not apply bulk operations directly from a selected grid.
- Record each create, update, delete, batch operation, and import with timestamp, affected records, before/after values where applicable, and outcome. Provide an operation-history link from success feedback.
- Create a database snapshot before imports and material batch operations. Identify the snapshot/operation reference in the result view.
- Confirm deletion, batch updates, and filesystem-changing imports with a dialog that names scope and irreversible effects.
- Retain unsaved input when database locking, validation, or filesystem access fails.
- Treat UI action visibility as guidance only; every protected request remains
  subject to Backend Reader, Writer, or Admin authorization.
- Never render or retain plaintext stored Tokens, token hashes, registration
  secrets, Bootstrap Codes, or Backend diagnostics outside the role-sensitive
  disclosure contract. One-time Token issuance is the sole permitted plaintext
  display.
- A rejected, cancelled, stale, repeated, or unauthorized action must not claim
  success and must preserve the applicable durable and filesystem state.

## Out of Scope

- Public access, username/password accounts, cloud synchronization, or
  client-side authorization policy. Approved device authentication and roles
  are in scope.
- A generic raw SQL table editor.
- Editing generated IDs, UUIDs, or audit timestamps.
- A top-level CRUD page for `album_model` or `album_relation`; both relationships are instead maintained in the Album form.
- Automated acceptance of AI suggestions.
- Exposure or conversion of archived historical `workspace_album` records. A
  future AI Collection Workspace requires UI-011A/B and a separately reviewed
  Promotion mapping.

## Acceptance Criteria

The plan is fulfilled when a local user can:

1. connect with an approved device Token and receive only the routes, actions,
   and diagnostic fields allowed by its effective Reader, Writer, or Admin role;
2. browse, search, create, and edit Models, Studios, Statuses, Albums, and Photos under the data interaction rules;
3. create Models and Studios either from their lists or without leaving Album/Import workflows;
4. use readable names for all foreign-key interactions and navigate to referenced entities;
5. add, remove, and edit Models / Additional Models from Album details, with those actions correctly creating, deleting, or updating `album_model` records rather than writing Model data to `album`;
6. add and remove logical/release Album links from Album details, with those actions correctly creating or deleting non-self `album_relation` records;
7. select folders, review parsed data/conflicts, and batch-import valid selections directly to `album` with related Studio, Model, `album_model`, and optional `album_relation` records;
8. receive preview, explicit confirmation, truthful per-item results, and auditable Operation links for material batches and imports;
9. inspect role-appropriate Operation history and follow supported links among
   Imports, Issues, Repairs, Snapshots, authentication events, and affected entities; and
10. use Admin-only authentication and recovery capabilities only after their
    controlling UI tasks and Backend contracts are Ready.

Future AI Collection Workspace acceptance is controlled separately by
UI-011A–D and is not satisfied by restoring the historical Workspace UI.

## Automated Test Layers

UI verification uses complementary layers and keeps each rule at the lowest
layer that can prove it clearly:

1. Backend unit, service, workflow, and API tests remain authoritative for
   business rules, durable side effects, authorization, and error contracts.
2. Browserless Web contract tests verify request/response mapping, rendering
   logic, and interaction rules with fast, focused feedback.
3. Focused Playwright workflow scripts verify complete feature journeys against
   disposable Backend resources.
4. The Playwright runner provides a shared real-browser smoke gate. Chromium is
   required for completed UI tasks; Chromium, WebKit, and Firefox form the
   opt-in release gate.

Real-browser tests must use UI-003 fixtures, must not access live Curator data,
and must retain screenshots, traces, video, console errors, page errors, and
failed-request evidence only for failed runs. Diagnostic attachments must not
contain plaintext Tokens, registration secrets, or Bootstrap Codes.
