# AIC-001 — Versioned AI Instruction Profile

## Task ID

`AIC-001` — Status: `Ready`

## Title

Manage, Snapshot, and Execute Versioned Curator AI Instructions and Prompts

## Goal

Replace code-owned fixed Vision/Writer prompts and label-only prompt versions
with an Administrator-managed, versioned AI Instruction Profile that Curator
resolves at Dispatch, snapshots immutably on every Work Item, and supplies to
`llama.cpp` on every model call.

## Current Baseline and Problem

- `VISION_PROMPT` and `WRITER_PROMPT` are constants in the AI Worker.
- `vision_prompt_version` and `writer_prompt_version` are stored in model
  configurations and Work Item snapshots, but currently act as labels rather
  than selecting the executed prompt content.
- Worker and Backend validators correctly remain stricter than model prose.
- The current Writer rule produces six unique names distributed as two 2-word,
  two 3-word, and two 4-word names.

The result is operationally safe but not centrally manageable or fully
reproducible from persisted configuration alone.

## Controlling Behavior Contract

### Profile identity and lifecycle

1. An AI Instruction Profile has a stable UUID, human-readable name, Worker
   kind, Dataset/schema applicability, lifecycle state, immutable version,
   creation actor/time, and canonical content hash.
2. A published version is immutable. Editing creates a new version; disabling a
   Profile affects future Dispatch only and never rewrites historical Work Items.
3. Exactly one explicit default published Profile may exist for each supported
   Worker kind/Dataset combination. Dispatch may select another compatible
   published version deliberately.
4. Profile text is bounded, UTF-8, contains no secrets or filesystem paths, and
   is treated as configuration—not executable code.

### Profile content

5. The first Profile format contains:
   - global role and operating principles;
   - prohibited identification and sensitive-attribute inference policy;
   - Dataset-level description policy;
   - Vision stage prompt template;
   - Writer stage prompt template;
   - output language and naming-style policy;
   - referenced Vision/Writer schema versions;
   - referenced deterministic validator-policy version;
   - instruction transport (`composed_prompt` initially);
   - bounded extension metadata for future provider adapters.
6. Templates use a small allowlisted placeholder vocabulary. Unknown,
   recursive, or missing placeholders prevent publication or Dispatch.
7. Untrusted model inputs such as Vision JSON are placed in explicit delimiters
   and described as data, never instructions.

### Resolution and immutable execution

8. Dispatch resolves the selected Profile version and stores a complete immutable
   snapshot on every Work Item: all effective instruction/prompt content,
   Profile/version identity, schema/validator versions, transport, canonical
   hashes, and composition version.
9. The Worker executes only the Work Item snapshot. It never fetches “latest”
   instructions after claim and never substitutes its bundled prompt silently.
10. Missing, malformed, hash-mismatched, incompatible, or unsupported snapshots
    fail the Work Item with a bounded diagnostic before model execution.
11. Prompt composition order is deterministic:

    ```text
    Global Curator Instruction
    → Dataset Instruction
    → Stage Instruction (Vision or Writer)
    → Output Contract
    → Delimited Current Evidence/Vision Data
    ```

12. The first transport is `composed_prompt`, passed through the existing
    non-interactive `llama.cpp` invocation. `chat_template_system` requires a
    later compatibility task proving the GGUF template and CLI behavior for each
    supported model family; it is not inferred automatically.

### Enforcement and authority

13. Instructions are advisory to the model. Authentication, authorization,
    Evidence Manifest scope, state transitions, output schemas, deterministic
    Worker validation, Backend validation, Review, and Promotion remain the
    non-bypassable authority boundaries.
14. The Backend rejects output whose Profile-referenced schema/validator policy
    does not match the Work Item snapshot.
15. Review Detail discloses the exact Profile name/version/hash and resolved
    stage prompt provenance used by the run without exposing secrets or absolute
    paths.

## Initial Default Profile

The migration/bootstrap Profile must reproduce current supported behavior:

- suggestion-only Album analysis;
- analyze only Backend-selected Manifest evidence;
- do not identify people;
- describe visually supported scene, composition, clothing, objects, actions,
  and atmosphere;
- do not infer ethnicity, nationality, religion, health, disability, pregnancy,
  sexual orientation, gender identity, political affiliation, socioeconomic
  status, or unverified personal relationships;
- return only the required JSON objects;
- Writer produces exactly two 2-word, two 3-word, and two 4-word unique English
  Album names using capitalized permitted words and the existing forbidden-name
  vocabulary.

## Component Scope

### Backend

- Canonical schema and ordered migration for Profile identity, immutable
  versions, lifecycle, content, and hashes.
- Admin-only list/detail/create-version/publish/disable APIs with optimistic
  concurrency and Operation evidence.
- Model Configuration compatibility and default/explicit Profile selection.
- Dispatch Preview disclosure and immutable Work Item Profile snapshot.
- Submission-time schema/validator compatibility checks and Review provenance.

### AI Worker and llama.cpp adapter

- Remove fixed prompt ownership from normal execution after migrated snapshots
  are available.
- Validate snapshot identity, hash, template placeholders, transport, and
  supported composition version before invoking a model.
- Compose Vision and Writer inputs deterministically and preserve bounded,
  redacted diagnostics.
- Continue corrective retries using the same immutable Profile snapshot.

### Web administration

- Add an Admin surface to inspect Profiles and immutable versions, create a new
  draft version, compare resolved content, publish/disable, and identify the
  default.
- Dispatch shows the selected Profile/version alongside model settings.
- Review shows executed Profile provenance and content hash.

### Evaluation and verification

- Deterministic composition golden tests.
- Validator parity tests between Worker and Backend.
- Prompt-injection/delimiter fixtures and invalid-placeholder cases.
- Migration and historical Work Item compatibility tests.
- Real-browser administration, Dispatch, execution, Review provenance, stale,
  permission, and interruption acceptance.
- Optional representative-model evaluation records instruction adherence and
  naming-rule success separately from deterministic product correctness.

## Out of Scope

- Training, fine-tuning, LoRA creation, or modifying GGUF weights.
- Treating model compliance as a replacement for deterministic validation.
- Automatically trusting a GGUF-provided Chat Template or system role.
- Arbitrary user-authored executable templates, scripts, tools, or network access.
- Per-Album free-form instruction overrides in the first version.
- Automatic Profile optimization based on production Review ratings.

## Dependencies

- `BT-045` — managed immutable model configuration snapshots.
- `BT-049` — two-stage schemas and result validation.
- `BT-054` through `BT-056` — Dispatch resolution and immutable Work Items.
- `UI-031` — existing AI Model Configuration administration patterns.
- Current Worker composed-prompt and corrective-retry implementation.

## Implementation Sequence

1. Establish the Profile schema, canonical hashing/composition rules, default
   Profile content, migration/backfill, and controlling Backend API contract.
2. Add Admin lifecycle APIs and immutable version persistence.
3. Bind compatible Profile selection to Model Configuration and Dispatch Preview;
   snapshot resolved content into every new Work Item.
4. Update Worker snapshot validation and deterministic composed-prompt execution,
   retaining a bounded migration compatibility path only where explicitly needed.
5. Add UI administration, Dispatch disclosure, and Review provenance.
6. Add golden, migration, service/API, Worker, browser, and representative-model
   evaluation coverage before retiring fixed prompt constants.

## Acceptance Criteria

- An Admin can create, publish, inspect, supersede, disable, and select compatible
  Profile versions without changing historical Work Items.
- Dispatch Preview identifies the exact effective Profile/version; execution
  stores its full resolved immutable snapshot and hashes.
- Editing or disabling a Profile after Dispatch cannot change a claimed or
  pending Work Item's model input.
- The Worker invokes `llama.cpp` with deterministic content derived only from the
  Work Item snapshot and rejects unsupported or corrupted snapshots first.
- Worker and Backend enforce identical schema/validator policy, including the
  2×2-word, 2×3-word, 2×4-word naming distribution.
- Review exposes sufficient Profile provenance to reproduce and compare runs.
- Reader/Writer/Admin boundaries, Evidence scope, Review, and Promotion authority
  remain unchanged.
- Existing installations receive a deterministic default Profile and retain
  readable historical evidence without fabricated prompt provenance.

## Risks and Decisions

- Instruction text consumes context tokens; publication must disclose bounded
  instruction size and reject configurations that cannot leave safe space for
  evidence and output.
- A content hash proves which text was used, not that the model obeyed it.
- Profile changes can materially affect output quality and require explicit
  versioning plus evaluation rather than in-place editing.
- `chat_template_system` remains a separate future adapter capability because
  behavior varies by model family, GGUF metadata, and llama.cpp build.
