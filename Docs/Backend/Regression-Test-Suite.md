# Backend Regression Test Suite

## Purpose

BT-017 defines a repeatable, specification-aligned entry point for the
implemented Curator Backend regression boundary. The suite uses only the
existing `unittest` runner and isolated in-memory databases, temporary paths,
and test doubles; it must not use the production database or Archive.

Run commands from the repository root:

```bash
python3 tools/web_ui/tests/run_regression.py all
```

Use a focused group while working on one boundary:

| Group | Command | Controlling specification | Coverage boundary |
| --- | --- | --- | --- |
| API | `python3 tools/web_ui/tests/run_regression.py api` | [API Specification](Specifications/API-Specification.md) and [API Contract](Specifications/API-Contract.md) | `/api/v1` envelopes, validation and error mapping, pagination metadata, and bearer-token authorization. |
| Repository | `python3 tools/web_ui/tests/run_regression.py repository` | [Repository Specification](Specifications/Repository-Specification.md) | Repository persistence, conflict behavior, and API-facing read-model shape. |
| Workspace | `python3 tools/web_ui/tests/run_regression.py workspace` | [Workspace Workflow](Specifications/Workspace-Workflow.md) | Workspace creation, persisted lifecycle state, valid transitions, and rejected invalid transitions. |
| Authentication | `python3 tools/web_ui/tests/run_regression.py authentication` | [Authentication](Specifications/Authentication.md) | Registration approval, token use, expiry, revocation, scope checks, and protected-route enforcement. |
| Snapshots | `python3 tools/web_ui/tests/run_regression.py snapshots` | [Snapshot Specification](Specifications/Snapshot-Specification.md) | Risk classification, creation, restore safety, retention eligibility, and protected cleanup behavior. |
| Operations | `python3 tools/web_ui/tests/run_regression.py operations` | [Operation Logging](Specifications/Operation-Logging.md) | Durable operation creation, status transitions, error and repair context, and workflow linkage. |
| Workflow | `python3 tools/web_ui/tests/run_regression.py workflow` | [Testing Strategy](Testing-Strategy.md) and applicable workflow Specifications | UI-independent workflow sandbox isolation, durable-state assertions, repeatable scenarios, and completed workflow acceptance coverage. |

`all` uses test discovery to run every Backend test module, including the
workflow acceptance foundation and focused import, repair, issue, and
canonical-path coverage that supports the boundaries above. A test class and
test method name identify the affected contract or transition in failure output.

## Verification convention

Before completing a Backend change, run its named group, then run `all` twice
from a clean working tree. The HTTP API group opens an ephemeral loopback port
for its contract tests. A failure must be treated as evidence about the named
Specification boundary; tests do not redefine a Specification to match an
implementation.
