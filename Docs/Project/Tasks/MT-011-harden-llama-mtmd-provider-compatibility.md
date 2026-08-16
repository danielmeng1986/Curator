# MT-011 — Harden llama-mtmd Provider Compatibility

## Task ID

`MT-011` — Status: `In Progress`

## Title

Make the AI Worker Compatible and Diagnosable Across Supported llama-mtmd Builds

## Related Specification(s)

- [Backend Architecture](../../Backend/Backend-Architecture.md), out-of-process
  AI Worker API-client boundary.
- [API Specification](../../Backend/Specifications/API-Specification.md), Work
  Item failure and attempt-audit contract.
- [AI Worker deployment manual](../../User-Manual/zh-CN/worker/ai-worker.md),
  local llama.cpp, model-root, and projector configuration.

## Goal

Let a claimed Album Name Analysis Work Item invoke a supported
`llama-mtmd-cli` build without passing CLI-specific unsupported options, and
make model-process failures actionable without exposing secrets, prompts, or
private Evidence paths.

## Scope

- Remove the `llama-cli`-specific `--no-display-prompt` option from the
  `llama-mtmd-cli` invocation profile.
- Keep bounded multimodal arguments for the model, projector, context,
  threads, GPU layers, output tokens, temperature, images, and image-token
  budget.
- Preserve bounded JSON-object extraction when llama.cpp emits ordinary
  informational output around the model response.
- Capture process exit status and a bounded, sanitized stderr diagnostic for
  the local operator and the existing Work Item failure record.
- Categorize executable/argument, timeout, model-load, projector, GPU/backend,
  context/token-budget, and invalid-output failures where reliably possible.
- Add a startup or smoke-test compatibility check that fails before claiming
  work when the selected executable lacks required multimodal options.
- Add regression tests and update the English and Chinese Worker manuals with
  model-family sizing guidance and a manual one-image smoke test.

## Out of Scope

- Changing the Backend API, schema, claim, lease, Dispatch, or Evidence
  contracts.
- Encoding Qwen-specific minimums as global Backend validation rules.
- Automatically downloading or replacing models, projectors, or llama.cpp.
- Sending complete prompts, Evidence paths, Tokens, environment variables, or
  unbounded llama.cpp output to Backend logs.
- Rewriting historical Work Item configuration snapshots after an Admin edits
  a Model Configuration.

## Dependencies

- `MT-009` — runnable WSL2 AI Worker.
- `MT-010` — capability-aware waiting and automatic claim lifecycle.
- `BT-045` — versioned, portable AI Model Configuration contract.

## Implementation Steps

1. Separate the `llama-mtmd-cli` argument profile from options that are valid
   only for another llama.cpp CLI.
2. Add deterministic subprocess-result handling that retains a safe,
   size-bounded diagnostic while preserving the original exception cause.
3. Map timeouts and confidently recognizable provider failures to truthful
   Worker error codes; use a generic bounded provider failure otherwise.
4. Add capability/preflight coverage for required `--mmproj`, `--image`,
   `--image-max-tokens`, and GPU-layer options.
5. Add tests for successful noisy JSON output, unsupported arguments, non-zero
   exit, timeout, sanitization, truncation, and absence of secrets/private
   Evidence paths.
6. Extend the bilingual manual with Qwen2.5-VL sizing guidance, while clearly
   identifying it as model-family guidance rather than a global Curator rule.

## Acceptance Criteria

- The current supported `llama-mtmd-cli` build receives no
  `--no-display-prompt` argument.
- A one-image Qwen2.5-VL smoke run can load the configured main model and
  projector and return a JSON object through the Worker provider.
- A non-zero llama.cpp exit tells the local operator whether the failure was
  caused by argument parsing, model/projector loading, GPU initialization,
  timeout, context pressure, or an unknown provider error when that distinction
  is present in safe stderr.
- Diagnostics are bounded to the Backend error-message limit and contain no
  Device Token, prompt body, private Evidence path, or retained Evidence bytes.
- Provider failure never submits a partial Vision or Writer result and still
  truthfully ends the owned attempt as Failed.
- Editing an AI Model Configuration affects only future Dispatch snapshots;
  existing Work Items remain immutable and require deliberate Group closure and
  redispatch when sizing changes.

## Verification

- `python3 -m unittest workers.ai_worker.tests.test_worker`
- Disposable provider tests for success, unsupported option, timeout, stderr
  sanitization, and JSON extraction.
- Manual WSL2 one-image smoke run with the deployed Qwen2.5-VL model/projector.
- End-to-end sequence: Dispatch → claim → Evidence transfer → Vision → Writer
  → `ReadyForReview`.

## Risks or Notes

- llama.cpp multimodal support changes quickly. Capability checks and truthful
  diagnostics reduce upgrade risk but do not make every upstream build
  compatible.
- Qwen2.5-VL warns that some grounding tasks need at least 1024 image tokens.
  With eight images, the context must also leave room for prompt and generated
  output; `context_size=16384` and `image_max_tokens=1024` are the initial
  controlled-test values, not universal defaults.
