# Curator Database Model

> Documentation status: Current
> Owner: Database
> Last verified: 2026-08-11

## Purpose

Curator's database is too large for one useful ER diagram. This document is the
physical-model index. Start with the overview, then open only the domain relevant
to the task. Use [Schema Catalog](Schema-Catalog.md) for lifecycle, authority,
and constraint details; diagrams are navigation aids, not schema source.

## Diagram index

| Diagram | Covers |
| --- | --- |
| [System Overview](Diagrams/00-System-Overview.md) | Domain ownership and cross-domain flow |
| [Asset Catalog](Diagrams/01-Asset-Catalog.md) | Album, Photo, Model, Studio, Status, and Album relationships |
| [Authentication](Diagrams/02-Authentication.md) | Device registration, Token, renewal, and first-Admin bootstrap |
| [Operations, Repair, Recovery](Diagrams/03-Operations-Repair-Recovery.md) | Import claims, Operations, Issues, Repair, Quarantine, Snapshot and Restore claims |
| [Work Dispatch](Diagrams/04-Work-Dispatch.md) | Batch, Group, exclusive Album reservation, Item adapter, claim, and closure |
| [AI Workspace](Diagrams/05-AI-Workspace.md) | Dataset/configuration, Work Item execution/evidence, review/rework, Promotion, and retention |

## Cross-domain rules

- Backend owns all database access; clients use authenticated REST APIs.
- Album is the apps.web digital-asset management unit. Photo is catalog/evidence
  data, not a general Photo browser in apps.web.
- Album business Status is independent of Dispatch, Worker execution, and review state.
- `album_work_reservation` is the single active Album lock across Worker kinds.
- Claim tables bind reviewed previews to one execution; they are not business outcomes.
- Operation and immutable decision/result records preserve evidence after active
  projections change or reservations are released.
- Historical `workspace_album` is intentionally absent from active diagrams.
  DBDOC-005 preserves its retired model separately.

## Physical-model authority

See [Schema Source of Truth](Schema-Source-of-Truth.md). Until BT-059 is
complete, base schema, migrations, and Repository compatibility DDL have the
split authority documented there. Never infer a missing FK or constraint merely
from a Mermaid edge.
