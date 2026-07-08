# Curator Migration Task Specification

## 1. Purpose

This specification defines the standard process for performing controlled migration operations in Curator, especially when one model must be merged into another model due to alias resolution or identity correction.

The migration workflow must preserve data integrity, keep filesystem operations deterministic, and allow manual review before irreversible changes are applied.

## 2. Scope

This specification applies to migrations that involve:

* Reassigning albums from one model to another
* Rebuilding album paths after model consolidation
* Updating `workspace_album` records
* Removing obsolete model records from the `model` table
* Moving album folders in the filesystem
* Detecting and resolving path conflicts
* Marking ambiguous cases for manual review

## 3. Definitions

### 3.1 Source Model

The model that will be merged into another model and eventually removed.

### 3.2 Target Model

The model that will remain after the merge and will absorb the source model’s albums.

### 3.3 Rename Plan

A preview of all planned path changes, showing:

* `current_path`
* `expected_path`
* conflict status
* manual review requirement
* optional suffix adjustments for collision avoidance

### 3.4 Manual Review

A state in which a record is not automatically migrated because the script cannot safely resolve a path conflict or a structural ambiguity.

## 4. Requirements

### 4.1 Database Integrity

Before any destructive operation, the script must verify:

* The source model exists
* The target model exists
* The source model is referenced by one or more `workspace_album` records
* The source model is no longer referenced before deletion from the `model` table

### 4.2 Path Rebuilding

The migration must not perform a naive string replacement.

The `expected_path` must be rebuilt from the target model identity, including:

* The top-level alphabet directory
* The model folder name
* The asset type layer, if present
* The studio layer
* The album folder name

This means the script must regenerate the path according to Curator’s canonical path rules.

### 4.3 Conflict Detection

The script must detect path conflicts before applying changes.

A conflict exists when the computed `expected_path` already exists or collides with another planned destination path.

If a conflict exists and cannot be resolved automatically, the record must be marked for manual review by setting `status_id = 1`.

### 4.4 Collision Handling

If the computed `expected_path` conflicts with an existing path in the target model’s namespace, the script may attempt suffix-based disambiguation.

If a safe unique destination still cannot be produced, the item must remain unchanged and be marked for manual review.

### 4.5 Filesystem Application

Filesystem changes must only be performed when the user explicitly enables apply mode, for example with `--apply`.

In preview mode, the script must only print the rename plan and make no filesystem changes.

### 4.6 Cleanup

After successful migration:

* Update the relevant `workspace_album` rows to the new model
* Move album folders from `current_path` to `expected_path`
* Delete the source model record only after confirming no remaining references exist
* Remove the source model folder only if it becomes empty or contains only hidden files and empty directories

## 5. Operational Workflow

### 5.1 Preview Mode

Default behavior.

The script must:

1. Load source and target models
2. Collect all affected `workspace_album` rows
3. Generate the rename plan
4. Check for collisions
5. Print a detailed preview
6. Mark unresolved conflicts for manual review in the plan output only

No files or database records are modified in preview mode.

### 5.2 Apply Mode

Activated by `--apply`.

The script must:

1. Recompute the rename plan
2. Revalidate every path
3. Move folders on disk
4. Update database references
5. Remove the source model if safe
6. Clean up empty source folders

If validation results differ from preview output, the script must stop rather than continue with stale assumptions.

## 6. Logging and Auditability

The script should log:

* Source model ID and target model ID
* Number of affected albums
* Planned path changes
* Collision decisions
* Manual review cases
* Filesystem move results
* Database update results
* Final cleanup results

Logs should be sufficient to reconstruct what happened during a migration.

## 7. Safety Rules

* Never delete a model record while it is still referenced
* Never apply filesystem changes without explicit apply mode
* Never rely on blind string substitution for path migration
* Never silently overwrite an existing album folder
* Never auto-resolve a conflict that cannot be proven safe

## 8. Expected Example

Source model: `Blake Bartelli`
Target model: `Blake Eden`

Example migration:

* `B/Blake Bartelli/p/Digital Desire/Blake Bartelli 1`
* becomes
* `B/Blake Eden/p/Digital Desire/Blake Bartelli 1`

If this destination already exists, the script must attempt a safe suffix adjustment. If still ambiguous, the record must be flagged for manual review.

## 9. Acceptance Criteria

A migration implementation is considered correct only if it satisfies all of the following:

* Produces a full rename plan before applying changes
* Correctly rebuilds paths using the target model structure
* Detects collisions before moving files
* Supports manual review for unresolved conflicts
* Moves folders only in apply mode
* Removes the source model only after reference checks pass
* Leaves the system in a consistent state after completion

# English Task Instruction for Copilot

Implement a reusable model merge migration workflow for Curator.

The script must support merging one model into another model by using `source_model_id` and `target_model_id`.

Required behavior:

1. Load the source model and target model from the `model` table.
2. Find all related `workspace_album` rows that reference the source model.
3. Generate a rename plan first, without modifying anything.
4. For each affected album, rebuild the destination path using the target model identity and Curator’s canonical path rules.
5. Do not use a simple string replacement for `current_path`.
6. Detect path conflicts before applying changes.
7. If a destination path already exists or collides with another planned path, try to resolve it by appending a suffix.
8. If a safe unique destination cannot be determined, mark the record with `status_id = 1` for manual review.
9. Print the full rename plan by default.
10. Only move folders and update records when `--apply` is explicitly provided.
11. After successful migration, verify that the source model is no longer referenced by any `workspace_album` row before deleting it from the `model` table.
12. Remove the old source model folder only if it is empty or contains only hidden files and empty directories.
13. Keep the workflow reusable so future merges can be executed by changing only the source and target model IDs.

Please include clear logging, deterministic behavior, and strong safety checks.
