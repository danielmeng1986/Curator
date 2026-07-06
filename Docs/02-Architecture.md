# 02 · Architecture

> System Architecture of Curator

---

# Overview

Curator is designed as a layered architecture for managing personal digital assets.

Instead of interacting directly with the original files, Curator introduces a structured workflow that separates immutable data, editable workspace, validation, planning, and final execution.

This separation ensures that every operation is:

- reproducible
- reviewable
- maintainable
- extensible

The architecture prioritizes long-term reliability over short-term convenience.

---

# High-Level Architecture

```
                +----------------------+
                |      Archive         |
                | (Original Assets)    |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |     Normalize        |
                |  Import & Analysis   |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |  Workspace Database  |
                |  Editable Metadata   |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |     Validation       |
                | Rules & Consistency  |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |    Rename Plan       |
                | Planned Operations   |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |      Commit          |
                | Execute Changes      |
                +----------+-----------+
                           |
                           v
                +----------------------+
                | Curator Database     |
                | Long-term Knowledge  |
                +----------+-----------+
                           |
                           v
                +----------------------+
                |     AI Services      |
                | Recognition & Search |
                +----------------------+
```

---

# Architectural Layers

## Archive Layer

The Archive contains the original digital assets.

Characteristics:

- immutable
- authoritative
- reproducible
- independent of Curator

Curator never relies on modifying the Archive to maintain metadata.

The Archive should always remain recoverable.

---

## Normalize Layer

Normalize transforms raw filesystem information into structured records.

Responsibilities include:

- scanning folders
- reading metadata
- standardizing names
- identifying entities
- generating import records

Normalize does not make permanent decisions.

Its role is to prepare data for later processing.

---

## Workspace Layer

Workspace is the editable representation of the Archive.

Everything requiring human review happens here.

Examples:

- rename candidates
- validation status
- manual corrections
- metadata enrichment

Workspace allows experimentation without affecting the Archive.

---

## Validation Layer

Validation ensures that imported information satisfies project rules.

Typical validations include:

- naming conventions
- duplicate detection
- missing metadata
- invalid relationships
- consistency checks

Validation should report problems rather than silently fixing them.

---

## Rename Plan Layer

Rename Plan separates planning from execution.

Instead of immediately modifying folders, Curator generates an explicit plan describing intended operations.

Advantages:

- reviewable
- reversible
- auditable
- reproducible

Rename Plan represents human intent.

---

## Commit Layer

Commit performs approved operations.

Examples include:

- renaming folders
- updating metadata
- generating exports

Only reviewed plans should reach this stage.

---

## Curator Database

The Curator Database stores long-term knowledge.

Unlike the Workspace, this database represents stable information.

Examples:

- Studios
- Models
- Albums
- Relationships
- AI-generated metadata
- User annotations

The database gradually evolves into the project's knowledge base.

---

## AI Layer

Artificial intelligence operates on structured knowledge rather than raw folders.

Possible responsibilities include:

- face recognition
- similarity search
- caption generation
- semantic search
- duplicate detection
- relationship inference
- recommendation

AI services should remain modular and replaceable.

---

# Data Flow

The architecture follows a one-way processing pipeline.

```
Archive

↓

Normalize

↓

Workspace

↓

Validation

↓

Rename Plan

↓

Commit

↓

Knowledge Database

↓

AI Analysis
```

Each stage consumes the output of the previous stage.

Earlier stages should not depend on later ones.

This minimizes coupling and improves maintainability.

---

# Separation of Responsibilities

Each architectural layer has a single primary responsibility.

| Layer | Responsibility |
|--------|----------------|
| Archive | Store original assets |
| Normalize | Convert filesystem into structured records |
| Workspace | Editable working state |
| Validation | Verify correctness |
| Rename Plan | Describe intended operations |
| Commit | Execute approved operations |
| Curator Database | Store long-term knowledge |
| AI | Generate additional knowledge |

This separation follows the Single Responsibility Principle at the system level.

---

# Design Principles

The architecture follows several guiding principles.

## Immutable Source

Original assets remain unchanged.

---

## Explicit Workflow

Every important operation should be visible.

---

## Human Review

Critical decisions require confirmation.

---

## Replaceable Components

Individual modules may evolve independently.

Changing one component should not require redesigning the entire system.

---

## Database-Centered Design

Business logic should operate on structured data rather than directly on filesystem paths.

---

## AI as an Extension

AI enriches knowledge.

It does not replace the core architecture.

---

# Future Evolution

The architecture intentionally leaves room for future modules.

Examples include:

- Vector Database
- Knowledge Graph
- OCR
- Speech Recognition
- Video Analysis
- Cloud Synchronization
- Distributed Processing

New modules should integrate through existing architectural layers instead of bypassing them.

---

# Summary

Curator separates permanent assets, editable data, validation, execution, and AI into independent architectural layers.

This separation makes the system:

- understandable
- testable
- maintainable
- extensible

The architecture is intended to support continuous evolution over many years without sacrificing clarity.

---

> Architecture should outlive implementation.

> Individual technologies may change.

> The architectural principles should remain stable.
