# AI Context

> This document is the primary entry point for AI assistants working on the Curator project.
>
> Before making architectural decisions, modifying code, or generating new components, read this document first.
> Optimize for long-term maintainability over short-term implementation speed.

---

# Project Overview

Curator is a **Personal Digital Asset Intelligence Platform**.

Its purpose is not simply to organize files, but to build a long-term knowledge system around personal digital assets.

The project combines:

- structured metadata
- human knowledge
- AI-assisted analysis
- reproducible workflows

to create a maintainable and extensible archive.

---

# Project Goals

Curator aims to provide:

- reliable metadata management
- reproducible asset organization
- AI-assisted understanding
- scalable architecture
- human-controlled decision making

The project should remain useful for many years, even as AI models and technologies evolve.

---

# Core Principles

Every contribution should follow these principles.

## 1. Archive is immutable

The Archive contains the original assets.

Never modify the Archive directly.

Every operation should be reproducible.

---

## 2. Workspace is editable

Workspace is the only place where data may be modified.

Workspace exists to:

- import
- normalize
- validate
- review
- generate rename plans
- prepare commits

---

## 3. Database is the Source of Truth

The database represents the current understanding of the archive.

Avoid inferring metadata repeatedly from filenames.

Instead, persist structured information inside the database.

---

## 4. Human approval comes first

AI may recommend.

Humans decide.

Examples:

AI may:

- recognize faces
- detect duplicates
- generate tags
- propose album names
- suggest captions

AI must not permanently modify user assets without confirmation.

---

## 5. Documentation is architecture

Documentation is considered part of the system.

When an architectural decision changes, update the documentation.

Do not rely solely on source code to explain system behavior.

---

# System Overview

Current high-level workflow:

Archive

↓

Normalize

↓

Workspace Database

↓

Validation

↓

Rename Plan

↓

Commit

↓

Curator Database

↓

AI Analysis

Future modules may extend this workflow without changing its core philosophy.

---

# Current Technologies

The implementation may evolve over time.

Current primary technologies include:

Backend

- Python

Database

- SQLite

Frontend

- Web-based UI

Development

- Git
- GitHub
- AI-assisted development

The technology stack is replaceable.

The architecture is not.

---

# AI Responsibilities

AI is expected to assist in:

- metadata generation
- semantic analysis
- duplicate detection
- similarity search
- face recognition
- object recognition
- caption generation
- workflow automation
- documentation
- code generation

AI is not responsible for making irreversible user decisions.

---

# AI Development Guidelines

When modifying Curator:

Always:

- understand the architecture first
- preserve existing design principles
- prefer extending the system over replacing it
- document significant architectural changes
- keep implementations modular

Avoid:

- introducing hidden behavior
- bypassing validation
- modifying Archive directly
- tightly coupling unrelated modules
- replacing human decisions with automatic AI actions

---

# Documentation Reading Order

When working on Curator, AI assistants should read documentation in the following order:

1. AI-CONTEXT.md
2. README.md
3. Relevant ADR documents
4. Architecture
5. Workflow
6. Data Model
7. AI
8. Roadmap

Only after understanding these documents should implementation begin.

---

# Coding Philosophy

Prefer:

small modules

clear responsibilities

explicit workflows

readable code

maintainable architecture

Avoid:

premature optimization

overengineering

hidden state

duplicated business logic

---

# Long-Term Vision

Curator is intended to become a long-lived platform.

The system should remain understandable years after its creation.

Every architectural decision should increase:

- maintainability
- readability
- reproducibility
- extensibility

rather than short-term convenience.

---

# Working With Multiple AI Assistants

Different AI assistants may participate in this repository.

Examples include:

- ChatGPT
- Codex
- GitHub Copilot
- Claude Code
- Cursor
- future AI development agents

No assistant owns the project.

The documentation is the shared knowledge source.

All assistants should follow the documented architecture rather than relying on previous conversations.

---

# If You Are an AI Assistant

Before writing code:

Understand the architecture.

Understand the workflow.

Respect the design principles.

Prefer improving the system over adding shortcuts.

When uncertain, preserve consistency rather than introducing new patterns.

The goal is not only to write working software.

The goal is to help Curator evolve into a maintainable Personal Digital Asset Intelligence Platform.
