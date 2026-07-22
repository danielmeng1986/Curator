# Curator Local Web UI Plan

This is the index for the modular UI requirements of the local Curator web application. The application operates on `database/Curator.db` and follows the data model in [Curator Database Model](../Database/Curator_Database_Model.md).

| Module | Contents |
| --- | --- |
| [01 — Foundation and Navigation](01_Foundation_and_Navigation.md) | Purpose, local-only constraints, route structure, visual language, and reusable UI patterns. |
| [02 — Data Interaction Rules](02_Data_Interaction_Rules.md) | System fields, foreign-key display, validation, deletion, editable fields, and Album–Model relationship rules. |
| [03 — Entity Management](03_Entity_Management.md) | Albums, including Models / Additional Models and logical/release links, plus Models, Studios, Statuses, and Photos. |
| [04 — Workspace Albums](04_Workspace_Albums.md) | Temporary `workspace_album` browsing, editing, review, batch-editing, and workspace-to-permanent link semantics. |
| [05 — Direct Album Import](05_Direct_Album_Import.md) | Folder discovery, reviewed bulk import to `album`, mappings, including optional logical/release links, conflicts, and results. |
| [06 — Safety and Acceptance](06_Safety_and_Acceptance.md) | Audit and recovery requirements, out-of-scope decisions, and acceptance criteria. |

## Reading Order

Read modules 01 and 02 first. Modules 03–05 define the page-specific behavior, while module 06 defines requirements that apply across the application.
