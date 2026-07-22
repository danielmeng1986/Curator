# Data Interaction Rules

## Common Rules

1. `id`, `uuid`, `created_at`, and `updated_at` are system-managed. They may appear in an optional read-only Record Details area, but are hidden from default grids and never editable.
2. Normal create/edit forms expose business fields only.
3. Foreign keys are always operated by readable entity labels, not raw integers.
4. Selectors support search and allow an empty value only if the database field is optional. Required references block saving until resolved.
5. Dates use readable local display and unambiguous form inputs. Long text expands in grids and uses multiline form controls. Paths use monospace text with a copy control.
6. Deletion is guarded: show affected relationships, and block deletion or require a dedicated resolution workflow when references exist.

## Album–Model Relationship Rule

The many-to-many relationship between Albums and Models is managed through the Album UI, not by exposing `album_model` as a table to users.

- An Album form contains a **Models / Additional Models** section.
- Users may add an existing Model, create a Model inline, remove a Model, and edit the relationship metadata (`age_when_shot`, `role`, `remarks`).
- Adding a Model does **not** update the `album` row with a Model value. The application creates an `album_model` row containing `album_id` and `model_id`.
- Removing a Model deletes the corresponding `album_model` row; it does not delete the Model entity.
- Editing the relationship metadata updates only the corresponding `album_model` row.
- A Model can appear only once in an Album. The UI prevents duplicate selections before saving.
- The Album form is the ownership point for these changes, and saving it persists Album fields and changed Album–Model relationships as one logical transaction.

## Album–Album Relationship Rule

Some Studios publish one logical Album through multiple separate releases. The Album detail page therefore also contains a **Belongs to / Related Releases** section. It manages `album_relation` without exposing raw relationship-table CRUD.

- The user selects one or more existing logical/canonical Albums by their readable title and Studio, never by an ID.
- Saving a selected `BELONGS_TO` relationship creates an `album_relation` row with the edited Album as `album_id` and the selected logical Album as `related_album_id`.
- Removing the selection removes that `album_relation` row only; neither Album entity is deleted.
- The current Album cannot be selected as its own related Album. No self/default relation is displayed or stored.
- Each `(album_id, related_album_id, relation_type)` relationship is unique. The UI prevents duplicate selections.

## Foreign-Key Labels

| Foreign key | UI label |
| --- | --- |
| `album.studio_id` | `studio.name` |
| `album.status_id`, `workspace_album.status_id` | `status.name` |
| `photo.album_id`, `workspace_album.album_id` | Album title, with Studio as supporting text when ambiguous |
| `album_model.model_id` | `model.display_name`, falling back to `primary_name` |
| `album_relation.album_id`, `album_relation.related_album_id` | Album title, with Studio as supporting text when ambiguous |
| `workspace_album.belongs_to_album_id` | Workspace Album title, with Studio name and workspace ID as supporting text; it is not a permanent `album.id` |

## Editable Fields by Table

| Table | UI-managed fields | Interaction requirements |
| --- | --- | --- |
| `model` | `display_name`, `primary_name`, `description`, `country`, `ethnicity`, `eye_color`, `natural_hair_color` | `display_name` is the primary label; search both names. |
| `studio` | `name`, `website`, `description`, `media_scope` | `name` is required; validate `website` as a URL when supplied. |
| `status` | `name`, `description` | Show as chips elsewhere; prevent deletion while used by Albums or Workspace Albums. |
| `album` | `studio_id`, `status_id`, `title`, `description`, `scene`, `location`, `capture_date`, `publish_date`, `rating`, `path` | `path` is the single canonical permanent location. The form also includes relationship sections whose writes go to `album_model` and `album_relation`, not `album`. Rating is a non-negative integer until a project range is defined. |
| `photo` | `album_id`, `filename`, `relative_path`, `hash`, `width`, `height`, `capture_time` | Normally managed in the parent album context. |
| `album_model` | `model_id`, `age_when_shot`, `role`, `remarks` | Implementation table for the Album form’s Models / Additional Models section; never presented as direct table CRUD. One model may occur once per album. |
| `album_relation` | `related_album_id`, `relation_type`, `remarks` | Implementation table for the Album form’s Belongs to / Related Releases section; never presented as direct table CRUD. The initial UI supports `BELONGS_TO`. |
| `workspace_album` | `current_path`, `expected_path`, `primary_model`, `studio_name`, `album_name`, `additional_models`, `status_id`, `remark`, `belongs_to_album_id`, `ai_result`, `album_id` | Temporary data. `belongs_to_album_id` selects a Workspace Album, while `album_id` selects a permanent Album; neither is entered as a raw ID. AI output is non-authoritative. |
