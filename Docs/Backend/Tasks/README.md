# Curator Backend Tasks

## Purpose

This directory is the implementation-planning layer for the Curator Backend. A Task document turns a bounded item from one or more Backend Specifications into independently implementable and verifiable work. It does not define new product behavior or override Architecture or Specifications.

The documentation hierarchy is:

```text
Vision
  ↓
Architecture
  ↓
Specification
  ↓
Task
  ↓
Implementation
  ↓
Testing
```

- **Architecture** defines enduring boundaries and responsibilities.
- **Specifications** define observable behavior and constraints.
- **Tasks** define a small, sequenced implementation unit that realizes specified behavior.
- **Implementation** contains the code, migrations, configuration, and tests that complete a task.

If a task exposes an ambiguity or missing decision, resolve the relevant Specification before implementation. A task must never silently invent backend behavior.

## Naming convention

Each task document uses this filename format:

```text
BT-<three-digit-sequence>-<short-kebab-case-title>.md
```

For example: `BT-003-shared-api-contract.md`.

Task IDs use the same `BT-<three-digit-sequence>` prefix. IDs are permanent: do not reuse an ID after a task is cancelled, superseded, or split. Mark the original document accordingly and create new IDs for replacement tasks. Use the next available sequence number rather than renumbering existing tasks.

## Creating a task

Start from [Task Template](Task-Template.md) and follow the [Task Decomposition Guidelines](Task-Decomposition-Guidelines.md). Link each task to the controlling Specification sections and keep its acceptance criteria observable. A task is ready for implementation only when its scope, dependencies, verification approach, and unresolved risks are explicit.

## Status and change control

Task documents may record a status near their Task ID (`Proposed`, `Ready`, `In Progress`, `Blocked`, `Complete`, or `Superseded`). Status does not replace source control history or test results. Update a task when its implementation boundary, dependencies, or verification evidence changes; do not use a task document to change a Specification.
