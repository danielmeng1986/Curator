# Workspace Albums

The Workspace area is for temporary processing and must be visibly marked **Workspace / temporary**. It supports review and correction without being confused with permanent knowledge.

## Browse and Filter

`/workspace/albums` provides filters for Status, Studio name, primary Model, linked/unlinked `album_id`, and text search across album name, paths, remarks, and AI result.

Default columns are primary model, studio name, album name, status, current path, expected path, and linked album. Other fields are available through column visibility controls.

## Detail View

`/workspace/albums/:id` groups editable fields into:

- **Identity and source** — primary model, studio name, album name, paths.
- **Review** — Status, remark, AI result. AI output is presented as a suggestion that a human must confirm or correct.
- **Links** — `belongs_to_album_id` is a searchable **Workspace Album** selector (because it references `workspace_album.id`); `album_id` is a separate permanent Album selector/link. When both workspace rows have permanent Album links, show the implied future `BELONGS_TO` relation as migration context. A self/default workspace relation (`belongs_to_album_id = id`) is represented as no selected parent in the UI and is not migrated to `album_relation`.

## Batch Editing

The list may batch-edit Status, Studio name, and explicitly supported text fields only. Before commit, it shows the affected-record count and all validation failures. It never permits raw bulk changes to system-generated or audit fields.
