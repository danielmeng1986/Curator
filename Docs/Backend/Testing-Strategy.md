# Curator Backend Testing Strategy

## 1. Purpose

Automated testing is a core part of the Curator Backend architecture. Its purpose is not only to show that code currently works, but to continuously verify that implementations remain compliant with the [Backend Specifications](Specifications/README.md).

This strategy does not replace individual Backend Specifications. Specifications define the required observable behavior; this document defines how implementations are verified against those contracts.

The testing architecture supports:

- reliable refactoring;
- safe feature development;
- regression prevention;
- specification compliance;
- continuous-integration automation; and
- AI-assisted development.

## 2. Testing Philosophy

### Specification First

Tests verify the Specification. They must not define behavior independently of it.

When a Specification and an implementation disagree, the Specification is the source of truth. A test that exposes such a disagreement is useful evidence for correcting the implementation, or for explicitly changing the Specification through the appropriate architectural process before changing the test.

### Repeatable

Every test must be repeatable: running the same test twice with the same inputs must produce the same result. Tests must not depend on existing production data, an operator's local working state, timing-sensitive assumptions, or outcomes left behind by earlier tests.

### Isolated

Tests execute against isolated resources. Production databases must never be modified, and production Archive folders must never be modified. Each test or test suite receives the data, configuration, filesystem locations, and external collaborators appropriate to its scope.

### Fast Feedback

Most tests should complete within seconds, allowing developers and AI coding agents to run them frequently during implementation and refactoring. Slower end-to-end or recovery scenarios remain valuable, but should be separated so they do not delay the normal feedback loop.

## 3. Testing Layers

The Backend uses complementary testing layers. A behavior should be tested at the lowest layer that can provide meaningful confidence, with higher layers reserved for integration and contract risks.

### Unit Tests

Unit tests verify pure business logic. Examples include:

- validators;
- naming rules;
- path normalization;
- state-transition rules; and
- helper utilities.

They should avoid databases and file systems whenever possible. Their purpose is quick, precise feedback on rules with clear inputs and expected outcomes.

### Service / Function Tests

Service / Function Tests verify individual backend services and operations. Examples include:

- Repository operations;
- Import services;
- Repair services; and
- Snapshot services.

These tests may use the sandbox database and a mock file system. They verify that a service coordinates persistence, filesystem collaborators, transactions, recovery behavior, and operation logging according to its applicable Specification.

### Workflow Tests

Workflow tests verify complete business workflows across Backend components. A representative workflow is:

```text
Import
  ↓
Workspace
  ↓
Issue creation
  ↓
Repair
  ↓
Snapshot
  ↓
Logging
  ↓
Completion
```

These tests ensure that hand-offs between services are correct, including expected state, records, recovery information, and side effects.

### API Contract Tests

API Contract Tests verify REST API behavior as experienced by clients, rather than internal implementation details. They cover:

- request validation;
- response schemas;
- HTTP status codes;
- error responses; and
- OpenAPI compatibility.

They protect the public `/api/v1` contract for the Web UI, AI Worker, CLI tools, and future clients.

## 4. Sandbox Environment

Automated tests use a dedicated sandbox environment. Example sandbox assets are:

```text
Curator-Sandbox.db
SandboxArchive/
SandboxWorkspace/
```

The sandbox must be disposable, reproducible, populated with deterministic data, and incapable of affecting production data. Test setup creates or restores the required sandbox state; test cleanup removes it or replaces it with a known baseline.

Every automated test executes only against sandbox resources or narrower test doubles. Test configuration must make the selected database and filesystem roots explicit so an implementation cannot silently fall back to production paths.

## 5. Mock File System

Many Backend workflows operate on files, but tests should not require a large real Archive. Use lightweight directory structures made from empty folders and placeholder files to represent the relevant conditions.

The objective is to verify Backend behavior—path calculation, validation, collision handling, moves or copies, compensation, and repair hand-off—not media processing. Tests that need filesystem failure behavior should simulate the smallest relevant failure while preserving deterministic results.

## 6. Best-Case and Worst-Case Testing

Testing must go beyond expected scenarios. Each applicable Specification should be represented by both successful and adverse cases.

Best-case examples include:

- valid metadata;
- a valid folder structure; and
- no conflicts.

Worst-case examples include:

- duplicated models;
- missing folders;
- invalid naming;
- corrupted workspace records;
- interrupted operations; and
- rollback scenarios.

The goal is to verify robustness, recovery, and clear failure behavior—not only successful correctness.

## 7. OpenAPI Integration

OpenAPI is the canonical description of the REST interface. The OpenAPI document should become the foundation for:

- API documentation;
- frontend client generation;
- backend request validation;
- contract testing;
- Postman collection generation; and
- future automation tools.

Avoid manually duplicating API definitions whenever possible. API Contract Tests should compare implementation behavior with the canonical interface so generated clients, documentation, and validation remain aligned.

## 8. AI-Assisted Development

The testing strategy supports AI coding agents as implementation collaborators. After a Backend change, an AI tool should be able to:

- build the project;
- execute automated tests;
- verify API contracts;
- detect regressions; and
- report failures with sufficient diagnostic information.

Test outputs should identify the relevant specification behavior, input condition, expected result, actual result, and any useful sandbox or operation context. The objective is autonomous implementation verification without requiring an agent to inspect or modify production data.

## 9. Manual Testing

Manual testing remains useful for exploratory testing, UI integration, usability verification, and debugging. It complements automated testing rather than replacing it.

Manual verification may reveal a scenario that deserves a new automated test. Once a behavior is stable and specified, its repeatable checks should be captured in the appropriate automated layer where practical.

## 10. Future CI Integration

Continuous integration will eventually execute the testing architecture in a clean, reproducible environment. Its architectural direction includes:

- running unit tests on every commit;
- running workflow tests before merge;
- generating coverage reports; and
- publishing OpenAPI validation reports.

No continuous-integration platform is selected by this strategy. Future implementation chooses the platform and tooling while preserving the isolation, repeatability, Specification-first verification, and diagnostic requirements defined here.

## Design Goals

This Testing Strategy remains implementation-independent. It does not prescribe a programming language, test framework, database library, HTTP framework, or build system. Those are implementation choices and may evolve—for example, if Backend modules use different languages—without changing the testing architecture described here.

The strategy is a long-term foundation for maintainable verification: Backend Specifications define the contract, implementations fulfill it, and automated tests continuously demonstrate compliance.
