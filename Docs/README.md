# Curator Documentation

> **Code implements behavior. Docs preserve intent.**

Welcome to the Curator Design Book.

This documentation is the long-term knowledge base of the Curator project. It describes **why the system exists, how it is designed, and the principles behind its implementation.**

Unlike source code, these documents are intended to remain stable over time. They preserve architectural decisions, project philosophy, and design intent, allowing both humans and AI assistants to understand the project consistently.

---

# What is Curator?

Curator is a **Personal Digital Asset Intelligence Platform**.

Its goal is **not** to become another media player or photo management application.

Instead, Curator provides a structured platform for organizing, validating, enriching, and understanding personal digital assets with the assistance of AI.

Digital assets may include:

- Images
- Videos
- Documents
- Music
- Game screenshots
- AI-generated content
- Other personal collections

The architecture is intentionally designed so that additional asset types can be integrated in the future.

---

# Design Philosophy

Several principles guide every design decision within Curator.

## Archive is permanent

The Archive is considered the original source of all assets.

It should never be modified directly.

Every operation should be reproducible from the Archive.

---

## Workspace is editable

All editing operations are performed inside the Workspace.

Workspace represents the current working state of the Archive.

Validation, review, AI analysis, and rename planning are all performed here.

---

## Database is the source of truth

Metadata should not be inferred repeatedly from filenames.

Instead, Curator stores structured knowledge inside its database.

The database represents the authoritative description of the collection.

---

## Human remains the final decision maker

AI is an assistant.

It may suggest:

- tags
- captions
- identities
- relationships
- similarity
- rename plans

However, operations that permanently modify user assets require human confirmation.

---

## Documentation is part of the system

Documentation is not an afterthought.

It is considered part of the architecture.

Every significant architectural decision should be documented.

---

# Documentation Structure

The documentation is organized into several independent chapters.

| File | Purpose |
|-------|----------|
| AI-CONTEXT.md | Entry point for AI assistants |
| 01-Vision.md | Project vision and philosophy |
| 02-Architecture.md | Overall system architecture |
| 03-Workflow.md | Data processing workflow |
| 04-Data-Model.md | Core concepts and data model |
| 05-AI.md | AI architecture and responsibilities |
| 06-Roadmap.md | Development roadmap |
| ADR/ | Architecture Decision Records |

Each chapter focuses on a single topic.

Whenever possible, implementation details should remain inside the source code, while long-term knowledge belongs inside these documents.

---

# Reading Order

For humans:

1. Vision
2. Architecture
3. Workflow
4. Data Model
5. AI
6. Roadmap

For AI assistants:

1. AI-CONTEXT.md
2. Vision
3. Architecture
4. Relevant ADR documents
5. Requested implementation files

---

# Architecture Decision Records (ADR)

Architectural decisions are stored separately under the `ADR/` directory.

Each ADR answers four questions:

- What decision was made?
- Why was it made?
- What alternatives were considered?
- What consequences does this decision introduce?

Once accepted, ADRs become part of the project's permanent design history.

---

# Updating Documentation

Documentation should evolve together with the project.

General guidelines:

- Keep concepts stable.
- Separate architecture from implementation.
- Record important decisions before they are forgotten.
- Prefer adding new ADRs instead of modifying historical decisions.
- Avoid documenting temporary implementation details.

---

# Scope

This documentation intentionally focuses on long-term design.

It does **not** attempt to replace:

- API documentation
- Source code comments
- SQL schema
- User manuals

Instead, it explains the reasoning behind the system.

---

# Audience

This documentation is written for:

- Future maintainers
- Contributors
- AI coding assistants
- The project owner
- Future versions of Curator

---

> Curator is not merely a software project.

> It is an evolving knowledge system for managing personal digital assets over the long term.
