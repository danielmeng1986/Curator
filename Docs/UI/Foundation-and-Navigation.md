# Foundation and Navigation

> Documentation status: Current
> Owner: UI
> Last verified: 2026-08-13

This document describes the shipped `apps.web` shell, routes, roles, and shared
visual patterns.

## Purpose and deployment boundary

Curator is a browser UI for reviewing and maintaining permanent entities and
running traceable operational workflows through the authenticated Backend API.
The Web client never opens the database directly.

The Backend binds to loopback by default. An operator may explicitly bind it to
a trusted home LAN so another device or AI Worker can connect. Device Tokens
with Reader, Writer, and Admin authorization apply in both modes; Curator does
not introduce username/password accounts. First-Administrator bootstrap remains
loopback-only, and all broader network behavior remains governed by the Backend
Authentication and deployment contracts.

## Route inventory

Routes below use the browser hash form implemented by the client.

| Route | Purpose | Role |
| --- | --- | --- |
| `#/` | Dashboard counts and actionable status. | Reader+ |
| `#/albums`, `#/albums/new`, `#/albums/:id` | Browse and manage Albums, Model links, related releases, and Album-owned Photo evidence. | Reader; writes require Writer |
| `#/models`, `#/models/new`, `#/models/:id` | Browse/manage Models and inspect linked Albums. | Reader; writes require Writer |
| `#/studios`, `#/studios/new`, `#/studios/:id` | Browse/manage Studios and inspect linked Albums. | Reader; writes require Writer |
| `#/statuses` | Maintain controlled Album statuses. | Reader; writes require Writer |
| `#/import/albums` | Compose, preview, and execute permanent Album imports. | Writer |
| `#/operations`, `#/operations/:uuid` | Inspect role-sensitive workflow history and evidence. | Reader+ with field-level disclosure |
| `#/issues`, `#/issues/:uuid` | Browse Issues and permitted decisions. | Reader+; decisions depend on role/policy |
| `#/repairs`, `#/repairs/:uuid` | Browse and act on Repair cases. | Reader+; actions depend on role/policy |
| `#/quarantine`, `#/quarantine/:uuid` | Review and restore quarantined assets. | Admin |
| `#/admin`, `#/admin/devices`, `#/admin/backups`, `#/admin/restore` | Device, Token, recovery-point, and database Restore administration. | Admin |
| `#/work-dispatch`, `#/work-dispatch/groups/:uuid` | Dispatch Albums and inspect active/history Groups. | Admin |
| `#/ai-workspaces`, `#/ai-workspaces/:uuid` | Inspect AI Workspace lifecycle and summary. | Admin |
| `#/ai-reviews`, `#/ai-work-items/:uuid/review` | Review Worker results and promote an approved Album name. | Admin |

Supported query parameters preserve applicable search, filter, pagination, tab,
and queue context. Authentication and in-progress secrets never appear in URLs.

## Application shell

The desktop-first shell contains:

- a persistent left rail containing role-permitted capabilities;
- a compact top bar for global search, connection or pending-registration
  state, database health, backup summary, and contextual action;
- a main content area with stable route-based recovery; and
- persistent resume entries for non-terminal workflows where required by the
  UI Specification.

Navigation visibility is guidance; Backend authorization remains authoritative
for every direct request.

## Visual character

Use a calm, dense, editorial style: neutral surfaces, clear type hierarchy,
modest borders, and one consistent primary-action accent. Status, validation,
permission, and selection never rely on color alone. Forms stack on narrow
screens; data-heavy grids remain optimized for desktop browsers.

## Reusable patterns

| Pattern | Current requirement |
| --- | --- |
| Data grid | Server-paginated where supported, sortable/filterable, URL-backed context where recovery matters, and explicit empty/loading/error states. |
| Detail form | Meaningful field groups, retained validation input, guarded navigation, and clear Save/Cancel actions. |
| Relationship selector | Searchable readable labels with a secondary identifier when needed; raw foreign keys are not the interaction surface. |
| Inline creation | Model and Studio creation preserves the owning Album/Import draft and selects the created entity after success. |
| Reviewed action | Material writes expose scope, Preview identity where required, explicit execution, and explicit cancellation; implicit dialog dismissal is not cancellation. |
| Feedback | Truthful success, partial, pending, and failure states with the next useful action and durable evidence link where available. |
| Empty state | Explains why content is absent and offers the permitted next action. |
