# AIC-002 — Grammar-Constrained Writer Decoding

## Task ID

`AIC-002` — Status: `Complete`

## Goal

Move the Album Writer from prompt-only formatting to llama.cpp constrained
decoding so malformed JSON and the wrong 2/2/3/3/4/4 name distribution cannot
be generated, while retaining deterministic Worker and Backend validation.

## Contract

1. Writer-capable llama.cpp builds must expose `--grammar`; compatibility is
   checked before the Worker claims work.
2. Curator owns a versioned GBNF grammar matching `writer-v1`. It fixes the
   object fields and six ordered name slots: two 2-word, two 3-word, and two
   4-word names.
3. Writer decoding uses temperature zero by default. A future reviewed policy
   may expose another bounded stage-specific value.
4. Prompt instructions remain necessary for meaning; grammar controls shape.
   Worker and Backend validators remain authoritative for uniqueness, forbidden
   words, capitalization, lengths, and schema semantics.
5. Corrective retries reuse the same grammar and frozen Instruction Profile.
6. Provider metrics disclose constrained-decoding policy and effective Writer
   temperature without persisting raw prompts or model output diagnostics.
7. An incompatible grammar sampler fails before submission; Curator never
   silently falls back to unconstrained Writer generation.

## Acceptance Criteria

- Writer invocations always include the reviewed grammar.
- The grammar admits the canonical Writer payload and structurally prevents an
  array with the wrong number or ordered word-count distribution.
- A Worker using a llama.cpp build without grammar support is rejected before
  claiming Work Items.
- Existing semantic validation and corrective retry tests remain green.
- Deployment documentation tells operators to migrate Backend separately and
  update/restart the out-of-process Worker after code changes.

## Implementation Evidence

- `workers/ai_worker/constraints.py` owns the reviewed
  `writer-v1-gbnf-1` grammar.
- Writer preflight requires `--grammar`; every invocation supplies the grammar
  and uses an effective temperature of zero without an unconstrained fallback.
- Provider runtime metrics record the constraint version and effective
  temperature.
- The installed llama.cpp CLI advertises `--grammar`, and 27 Worker plus 374
  focused Backend tests pass.
- The live Backend database was explicitly upgraded through migration `0017`;
  its Model Configuration now references the seeded Profile version.
- A WSL smoke run exposed a build-specific invalid escaped hyphen in the first
  grammar revision. The character class now places the hyphen last without an
  escape, and regression coverage classifies grammar parse failures explicitly.
- A second WSL smoke run exposed unbounded deterministic continuation inside a
  name word. Each word is now structurally bounded to 24 characters, preventing
  token-budget exhaustion before the JSON object closes.
