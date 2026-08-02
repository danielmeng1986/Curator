# Backend Task Decomposition Guidelines

## Purpose

These guidelines define how to turn Curator Backend Specification items into implementation tasks. They structure implementation work; they do not add, reinterpret, or prioritize backend behavior beyond the controlling Architecture and Specifications.

## Start with the specification boundary

Each task must cite the Specification section that controls it. Read that section first and identify its observable outcomes, invalid states, persistence effects, recovery behavior, and required verification. A task may implement part of a Specification, but it must not leave a specified behavior half-implemented behind an externally reachable endpoint.

When a Specification contains an unresolved question, the work is blocked until the question is resolved in the Specification or an approved ADR. Do not choose a product rule in code merely to make a task executable.

## Valid task boundaries

A valid task has one coherent outcome and a reviewable change boundary. It should normally be completable independently once its declared dependencies are satisfied, and it must have focused acceptance criteria and verification.

Useful task boundaries include:

- Establishing one cross-cutting contract, such as the shared API response envelope and error mapping.
- Moving one persistence capability behind a repository contract while preserving its existing service behavior.
- Implementing one complete workflow stage, such as import preview and validation before any write occurs.
- Adding a closed set of state transitions, their persistence, and transition tests.
- Introducing a canonical read model for one consumer-facing query and migrating its consumers.

A task may touch multiple files or layers when that is necessary to deliver one specified outcome. It must not combine unrelated workflows merely because they use the same database table or server module.

## Splitting a specification item

Decompose a Specification item along its externally meaningful stages and architectural boundaries:

1. Identify the behavior that can be completed without relying on unfinished behavior.
2. Separate foundations (contracts, canonical models, repository access, or path normalization) from workflows that consume them.
3. Keep validation-before-mutation separate from the mutation and compensation workflow when the Specification distinguishes them.
4. Keep transport adaptation separate from business-rule implementation unless both are needed for one small, usable vertical slice.
5. Add verification with the task that introduces the behavior, rather than deferring all tests to a later task.

The split must preserve the order implied by dependencies. For example, import execution depends on deterministic preview, validation, collision detection, canonical paths, repository access, and the required operation-recording foundation.

## Dependencies and blocked work

List dependencies by task ID, Specification decision, migration, fixture, or required infrastructure. State why each dependency matters. A task may begin preparatory work before a dependency completes only if it cannot create or expose behavior that assumes an unresolved dependency.

A task is **blocked** when completion cannot proceed without one of the following:

- a missing or contradictory Specification or ADR decision;
- an incomplete prerequisite task whose output is required for correctness;
- an unavailable required migration, test fixture, or integration environment; or
- a safety or recovery question that the Specification requires to be decided before mutation.

An implementation difficulty, a failing test, or a desire for a cleaner design is not by itself a blocked state. Record it as a risk or note and continue within the approved scope where possible.

## Completion and verification

A task is complete only when all of these are true:

- Its stated acceptance criteria are met without changing the controlling contract.
- Automated tests cover the task's successful and specified invalid or failure outcomes.
- Relevant existing regression tests pass.
- The task's dependency boundaries remain intact: controllers contain transport work, services contain application rules, and repositories own persistence access.
- Required documentation, migrations, and recovery evidence are updated.

Verification should use the narrowest reliable evidence first (unit tests for normalization or state transitions, repository tests for read-model mapping, API contract tests for serialization), followed by focused integration or end-to-end tests when a workflow spans resources.

## Granularity examples

### Good granularity

| Task scope | Why it is a valid task |
| --- | --- |
| Introduce the `/api/v1` success, error, and collection envelopes; route existing responses through them; test success, validation, and server-error serialization. | One shared public contract with clear compatibility tests. |
| Create canonical `AlbumListReadModel` mapping in the album repository and update the album-list service consumer. | One stable query result and its immediate consumer, without redesigning every entity. |
| Implement workspace `Active → Review → Closed` transition validation and persistence, with invalid-transition tests. | A closed lifecycle slice with explicit state-machine verification. |
| Add import preview duplicate and canonical-path collision checks that make no persistent changes. | One pre-write workflow stage with deterministic outcomes. |

### Too broad

| Overly broad scope | How to split it |
| --- | --- |
| “Refactor the whole backend into services and repositories.” | Split by capability: shared API contract, one repository boundary, then one service workflow at a time. |
| “Implement import.” | Split preview/validation, filesystem execution with compensation, and workflow regression coverage. |
| “Add authentication.” | Split device registration and approval, token lifecycle, authorization enforcement, and contract/regression tests where each can be verified. |
| “Normalize all backend models.” | Define and migrate one specified read model per consumer query, beginning with the active endpoints. |

## Task-writing checklist

Before marking a task `Ready`, confirm that it has:

- a permanent Task ID and filename following the directory convention;
- links to controlling Specification sections;
- one coherent goal and explicit exclusions;
- dependencies with reasons and any current blockers;
- small implementation steps that respect the architecture;
- acceptance criteria that can be observed; and
- a concrete verification plan covering success and specified failure paths.
