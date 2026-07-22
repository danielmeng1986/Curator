# Entity Management

## Albums

`/albums` is the permanent-data center. It searches title, Studio, location, scene, and linked Models; filters by Studio, Status, rating, capture/publish date range, and Model; and sorts by title, Studio, publish date, rating, and update time.

Rows show title, Studio, Status, linked Model names, dates, rating, and a compact path indicator. Eligible bulk metadata changes (for example, Status or Studio) require a review preview and must not silently replace non-empty values.

`/albums/new` and `/albums/:id` contain:

1. **Core metadata** — Studio, Status, title, description, scene, location, dates, rating.
2. **Storage** — the single canonical `path`, with a copy control and path validation warnings.
3. **Models / Additional Models** — the user-facing management surface for the Album–Model many-to-many relationship. Add existing Models, create Models inline, remove linked Models, and edit age when shot, role, and remarks. Adding/removing/editing this section creates/deletes/updates `album_model` rows only; it does not add Model data to the `album` row or delete Model entities.
4. **Belongs to / Related Releases** — the user-facing management surface for Albums that are separate releases of one logical Album. Add or remove a logical/canonical Album by readable title; the application creates or deletes `album_relation` rows with `relation_type = BELONGS_TO`. The current Album cannot relate to itself.
5. **Photos** — child records with add, edit, remove actions. Parent context sets the album reference.
6. **Record details** — read-only system fields.

The relationship sections are not `album_model` or `album_relation` table views: they show meaningful names, not raw IDs, and reject duplicate selections. Saving an Album and its relationship changes is one logical transaction. The result summarizes changed Album fields, added/removed/updated Model links, added/removed related-release links, and changed photos.

## Models and Studios

`/models` and `/studios` share browse-and-detail behavior: search, filter, sort, grid, direct creation, and details. Each may be created either from its dedicated list or from an Album/Import inline selector.

Model details show a read-only **Albums featuring this model** table. Selecting an Album opens its detail page, where the relationship is managed in the Album’s **Models / Additional Models** section. Studio details show **Albums from this studio**. Selecting a row opens the relevant album.

## Statuses

`/statuses` is a compact administration screen. It lists name, description, and usage counts in Albums and Workspace Albums. Editing updates the label globally. Deletion is enabled only when both usage counts are zero; otherwise the UI explains the references.
