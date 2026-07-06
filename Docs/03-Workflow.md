# 03 · Workflow

> Asset Processing Workflow

---

# Overview

Curator processes digital assets through a structured workflow.

Every asset follows the same lifecycle, regardless of its type.

The workflow separates discovery, validation, planning, execution, and knowledge generation into independent stages.

This ensures that every operation remains reproducible, reviewable, and maintainable.

---

# Workflow Overview

```
Archive

↓

Import

↓

Normalize

↓

Workspace

↓

Validation

↓

Review

↓

Rename Plan

↓

Commit

↓

Knowledge Database

↓

AI Enrichment
```

Each stage has a clearly defined responsibility.

A stage should never bypass another stage.

---

# Stage 1 — Archive

The Archive is the permanent storage of original assets.

Responsibilities:

- Store original files
- Preserve directory structure
- Preserve original filenames
- Remain immutable

Curator never edits files directly inside the Archive.

The Archive is considered the permanent source of digital assets.

---

# Stage 2 — Import

Import discovers assets from the Archive.

Typical operations include:

- scanning directories
- detecting new folders
- reading filesystem information
- collecting metadata
- creating import records

Import should never modify data.

Its purpose is discovery only.

---

# Stage 3 — Normalize

Normalize converts raw filesystem information into structured records.

Typical operations include:

- normalize naming
- identify studio names
- identify albums
- identify models
- generate standardized paths
- detect inconsistencies

Normalize prepares data for later processing.

It does not make permanent decisions.

---

# Stage 4 — Workspace

Workspace represents the editable working state.

Typical activities include:

- correcting names
- assigning models
- confirming studios
- editing metadata
- reviewing AI suggestions

Workspace allows experimentation without affecting the Archive.

---

# Stage 5 — Validation

Validation verifies whether the Workspace satisfies project rules.

Examples include:

- naming rules
- duplicate detection
- missing metadata
- invalid relationships
- inconsistent data

Validation should produce reports rather than silently modifying data.

Human users decide how to resolve issues.

---

# Stage 6 — Review

Review is the human decision stage.

Typical review tasks include:

- approve rename suggestions
- verify AI recognition
- inspect validation warnings
- resolve ambiguities

Curator intentionally separates review from automation.

AI may assist.

Humans approve.

---

# Stage 7 — Rename Plan

Rename Plan records every approved filesystem operation.

Typical operations include:

- rename folders
- rename files
- move assets
- create directories

Rename Plan exists before any filesystem changes occur.

Advantages include:

- preview
- auditability
- rollback capability
- reproducibility

Rename Plan represents human intent.

---

# Stage 8 — Commit

Commit executes approved plans.

Responsibilities include:

- apply filesystem changes
- update metadata
- synchronize databases
- generate logs

Commit should be deterministic.

The same Rename Plan should always produce the same result.

---

# Stage 9 — Knowledge Database

Once committed, information becomes part of Curator's long-term knowledge.

Examples include:

- studios
- models
- albums
- asset relationships
- user annotations
- semantic metadata

The Knowledge Database continuously evolves.

Unlike the Workspace, it represents stable knowledge.

---

# Stage 10 — AI Enrichment

Artificial intelligence enriches existing knowledge.

Possible tasks include:

- face recognition
- object recognition
- image captioning
- semantic tagging
- duplicate detection
- similarity search
- recommendation
- knowledge graph generation

AI enriches knowledge without replacing human authority.

---

# Human and AI Collaboration

Curator follows a collaborative workflow.

AI responsibilities:

- analyze
- suggest
- classify
- recognize
- recommend

Human responsibilities:

- review
- approve
- reject
- correct
- curate

This separation keeps important decisions transparent.

---

# Workflow Principles

Every workflow follows these principles.

## Reproducible

Every result should be reproducible from the Archive.

---

## Reviewable

Important changes should be inspectable before execution.

---

## Incremental

Processing should happen in small, manageable steps.

---

## Traceable

Every important operation should leave a history.

---

## Reversible

Whenever possible, changes should be recoverable.

---

## Extensible

Future processing stages may be inserted without redesigning the workflow.

---

# Error Handling

Errors should be reported as early as possible.

Examples include:

- invalid naming
- missing metadata
- conflicting identities
- duplicate folders

Whenever possible:

- detect
- report
- review
- resolve

Avoid automatic correction unless explicitly approved.

---

# Future Workflow Extensions

The workflow is intentionally extensible.

Future stages may include:

- OCR
- speech recognition
- video understanding
- cloud synchronization
- vector embedding
- semantic indexing
- knowledge graph construction

These extensions should enrich the workflow rather than replace it.

---

# Summary

Curator transforms raw digital assets into structured knowledge through a reproducible workflow.

Each processing stage has a single responsibility.

By separating discovery, normalization, validation, planning, execution, and AI enrichment, Curator maintains a clear distinction between original assets and accumulated knowledge.

---

> Every asset enters Curator as a file.

> Every asset leaves the workflow as structured knowledge.
