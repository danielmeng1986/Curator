# BT-045 — Establish Managed llama.cpp Model Configuration Contract

## Task ID

`BT-045` — Status: `Complete`

## Title

Manage Versioned llama.cpp Model Configurations

## Related Specification(s)

- UI-011A AI Collection Workspace Specification, model configuration section.
- `config/ai.toml` Vision/Writer prompts and `tools/dev/benchmark` parameter matrix.

## Goal

Provide centrally managed, comparable llama.cpp model configurations while
keeping host-local executable/model paths outside portable Backend data.

## Scope

- `ai_model_configuration` identity, name, provider, model repository/file,
  sample count, prompt versions, and important llama.cpp parameters.
- Parameters including context size, threads, GPU layers, maximum tokens,
  temperature, image token limit, and bounded additional JSON.
- Admin CRUD/enable-disable and Writer read-only discovery APIs.
- Immutable configuration snapshot captured by every accepted Work Item run.

## Out of Scope

- Persisting secrets or host-specific executable/absolute model paths.
- Installing models or controlling a remote Windows service.

## Dependencies

- Approved UI-011A configuration vocabulary and validation limits.
- BT-044 Dataset/schema boundary.

## Implementation Steps

1. Define portable fields, validation, versioning, and local Worker resolution rules.
2. Add schema, repository/service, Admin mutations, and Writer read APIs.
3. Add validation, authorization, snapshot immutability, and redaction tests.

## Acceptance Criteria

- Disabled configurations cannot be selected for new work.
- Updating a configuration never changes a prior run snapshot.
- Writer reads expose execution parameters but no host paths or secrets.
- Invalid or unbounded llama.cpp parameters are rejected with structured errors.

## Verification

- Repository/service/API tests using multiple benchmark-derived configurations.
- AI Worker configuration-resolution contract tests and full regression.

## Risks or Notes

- Prompt text versus prompt-version storage must be resolved by UI-011A; every
  result must remain reproducible enough to compare quality and runtime.

## Completion Record

- Added the explicit `0004` migration and portable llama.cpp configuration repository/service.
- Added Admin create/update/enable-disable and Writer enabled-only discovery APIs.
- Enforced benchmark-derived parameter bounds and rejected absolute paths or secret-like extras.
- Verified immutable snapshots across later updates; 694 complete regression tests passed.
