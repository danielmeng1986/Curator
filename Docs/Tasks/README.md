# Curator Documentation Tasks

## Purpose

This directory owns maintenance of Curator's documentation system. `DOC-*`
tasks govern cross-document authority, navigation, architecture, and conceptual
models. `DBDOC-*` tasks govern database documentation, diagrams, catalogs, and
schema-drift checks.

These tasks are intentionally separate from Backend implementation (`BT-*`),
Web UI (`UI-*`), and repository migration (`MT-*`) tasks. If documentation work
discovers an implementation gap, create the appropriate task in the owning
series rather than silently changing behavior from a documentation task.

## Naming and status

- Cross-document tasks: `DOC-<three-digit-sequence>-<short-title>.md`
- Database-documentation tasks: `DBDOC-<three-digit-sequence>-<short-title>.md`
- Status is one of `Proposed`, `Ready`, `In Progress`, `Blocked`, `Complete`,
  or `Superseded`.

## Task index

| Task | Outcome | Status |
| --- | --- | --- |
| [DOC-001](DOC-001-establish-documentation-authority-and-lifecycle.md) | Documentation authority, lifecycle, and conflict rules | Complete |
| [DBDOC-001](DBDOC-001-establish-database-schema-source-of-truth.md) | Authoritative database-schema source and ownership rules | Complete |
| [DBDOC-002](DBDOC-002-build-current-database-schema-catalog.md) | Complete machine-scannable current table catalog | Complete |
| [DBDOC-003](DBDOC-003-split-database-mermaid-model-by-domain.md) | Database overview and domain-specific Mermaid diagrams | Proposed |
| [DBDOC-004](DBDOC-004-document-persistence-workflow-boundaries.md) | Persistence maps for core cross-table workflows | Proposed |
| [DBDOC-005](DBDOC-005-archive-historical-workspace-and-v02-guidance.md) | Historical schema guidance isolated from active truth | Proposed |
| [DOC-002](DOC-002-refresh-ai-agent-context-and-documentation-index.md) | Accurate AI entry point and documentation navigation | Proposed |
| [DOC-003](DOC-003-reconcile-conceptual-data-model.md) | Conceptual model aligned with implemented and future domains | Proposed |
| [DOC-004](DOC-004-convert-backend-architecture-to-as-built.md) | Backend architecture rewritten as current as-built truth | Proposed |
| [DBDOC-006](DBDOC-006-add-schema-documentation-drift-gate.md) | Automated detection of schema-documentation drift | Proposed |

## Recommended execution order

`DOC-001 → DBDOC-001 → DBDOC-002 → DBDOC-003 → DBDOC-004 → DBDOC-005 → DOC-002 → DOC-003 → DOC-004 → DBDOC-006`

Authority and schema ownership come first. The catalog then supplies the facts
used by diagrams and workflow maps. Navigation and higher-level architecture
are refreshed after those facts are stable. The drift gate is last because it
must validate the finalized documentation contract rather than invent it.
