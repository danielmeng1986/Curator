# Foundation and Navigation

## Purpose and Scope

Curator is a local-only web application for reviewing and maintaining permanent
entities (`model`, `studio`, `album`, and `photo`), controlled statuses, and
traceable operational workflows through the authenticated Backend API. The Web
UI never opens the database directly. The Album–Model many-to-many relationship
is a user-managed part of Album editing: users add, remove, and edit Models in
an Album’s **Models / Additional Models** section. The application persists
those relationship changes in `album_model`; users never operate a raw
`album_model` CRUD screen. The same Album detail page manages logical/release
grouping through `album_relation`, without exposing a raw relationship-table
screen.

The Backend binds to a local address such as `127.0.0.1` by default. The UI uses
approved device Tokens with Reader, Writer, and Admin authorization; it does not
introduce username/password accounts. Explicit LAN deployment remains governed
by the Backend Authentication and deployment contracts.

## Routes

| URL | Purpose | Primary table(s) |
| --- | --- | --- |
| `/` | Dashboard with counts, recent changes, and actionable workspace items. | Read-only summary |
| `/albums`, `/albums/new`, `/albums/:id` | Manage permanent albums, Models / Additional Models, related releases, and photos. | `album`, `album_model`, `album_relation`, `photo` |
| `/models`, `/models/new`, `/models/:id` | Manage models and inspect their linked albums. | `model`, `album_model` |
| `/studios`, `/studios/new`, `/studios/:id` | Manage studios and inspect their albums. | `studio`, `album` |
| `/statuses` | Maintain controlled statuses. | `status` |
| `/import/albums` | Preview and batch-import folders to permanent albums. | `album`, `studio`, `model`, `album_model` |
| `/operations`, `/operations/:uuid` | Inspect role-sensitive workflow history and linked evidence. | Operation read models |
| `/issues`, `/issues/:uuid` | Review Issues and permitted Repair decisions. | Issue / Repair read models |
| `/admin` and child routes | Admin-only device, Token, Backup, Snapshot, Restore, and safety workflows. | Administrative read models |
| `/workspace`, `/workspace/:uuid` | Future dataset-aware AI Collection review; unavailable until UI-011A/B contracts and APIs are complete. | Versioned Workspace read models, not historical `workspace_album` |

Query parameters preserve filters, sorting, pagination, and open tabs. For example: `/albums?studio=MetArt&status=IMPORTED&sort=publish_date:desc`.

## Visual Language and Layout

The desktop-first application shell contains a persistent left rail for
available role-permitted capabilities, a compact top bar (global search,
connection/current-device state, database health/last backup, current-page
action), and a main content area. Workspace navigation is absent until the new
AI Collection Workspace is specified and implemented. Administrator navigation
is visible only to Admin devices, while Backend authorization remains
authoritative for direct requests.

Use a calm, dense, editorial style: neutral surfaces, clear type hierarchy, modest borders, and one consistent primary-action accent. Status chips, validation icons, and helper text must not rely on color alone. Forms stack on narrow screens; data-heavy grids remain optimized for desktop browsers.

## Reusable UI Patterns

| Pattern | Requirement |
| --- | --- |
| Data grid | Server-paginated, sortable, with column visibility, saved filters, and eligible row selection. |
| Detail form | Meaningful field groups and a sticky action bar for Save, Cancel, and scoped actions. |
| Relationship selector | Searchable combobox that shows a meaningful entity label and secondary identifier when useful. |
| Inline creation | `Create new…` in Model and Studio selectors opens a compact form, retains the active draft, and selects the created entity on success. |
| Change review | Every multi-record write previews inserts, updates, warnings, and conflicts. |
| Feedback | Clear success/error feedback; failed writes retain entered values. |
| Empty state | Explain why no data is shown and provide the relevant creation/import action. |
