# BT-067 — Persist AI Review Translation Cache

## Task ID

`BT-067` — Status: `Complete`

## Title

Add Backend-Owned On-Demand DeepL Translation and Persistent Review Cache

## Related Specification(s)

- [Work Dispatch Workflow](../Specifications/Work-Dispatch-Workflow.md), AI Review read model and immutable result evidence.
- [API Specification](../Specifications/API-Specification.md), Admin AI Review routes and error envelope.
- [Authentication](../Specifications/Authentication.md), Admin-only external-service use and secret handling.
- [Operation Logging](../Specifications/Operation-Logging.md), paid/external integration evidence.
- `BT-050`, `BT-058`, `UI-027`, and `UI-038`.

## Goal

Allow an Administrator to request Simplified Chinese assistance for the English
AI Recommendation titles of one Review item. Translate only cache misses,
persist the derived translations independently from immutable AI results, and
reuse them on every later read.

## Contract Decisions

1. AI result JSON remains immutable and authoritative. Translation is labelled
   machine-generated review assistance and never becomes a Promotion candidate
   or rewrites the English Recommendation.
2. The initial provider is DeepL. The Backend reads the credential only from
   `CURATOR_DEEPL_API_KEY`; it is never accepted from an API request, returned
   to a client, stored in SQLite/config JSON, or written to logs.
3. `CURATOR_DEEPL_API_PLAN=developer|growth` selects the current DeepL plan.
   Developer uses the API endpoint accepted by Developer keys (currently
   `api-free.deepl.com`); Growth uses `api.deepl.com`. Endpoint selection stays
   Backend-owned so future DeepL plan migrations do not change the Web client.
   Missing/invalid configuration disables translation with a stable readiness
   reason while leaving Review fully usable.
4. Backend configuration loads secrets in this precedence order: an existing
   process environment variable wins; otherwise the repository-root `.env`
   supplies the value; otherwise translation is disabled. Loading `.env` must
   not overwrite an explicitly supplied environment variable.
5. The real `.env` is Git-ignored and must be a regular file readable only by
   its owner (`0600`). An absent file is allowed; an unsafe permission, symlink,
   malformed assignment, or duplicate secret fails closed for translation and
   produces a redacted configuration diagnostic. `.env.example` is committed
   with empty values only.
6. Cache identity binds normalized source text, SHA-256 source hash, target
   locale (`zh-CN`, mapped to DeepL `ZH-HANS`), provider, provider model/quality mode, and translation
   format version. A source-text change is a cache miss; old evidence is not
   silently relabelled.
7. One request resolves all Recommendation titles for one Work Item. The
   Backend returns cached rows immediately and sends only missing unique texts
   in one bounded provider request.
8. Provider timeout, quota, authentication, malformed response, or partial
   response never changes Review state, draft, decision, Promotion, or source
   result. No success is assumed and no empty translation is cached.

## Scope

- Add an ordered migration and `ai_review_translation_cache` persistence with
  source text/hash, target locale, translated text, provider/model/format,
  timestamps, and unique cache identity.
- Add a provider-neutral translation adapter and a DeepL implementation using
  bounded HTTPS requests, explicit timeout, safe retry policy, response-size
  limits, and redacted diagnostics.
- Add a dependency-free, narrowly parsed `.env` Secret loader for
  `CURATOR_DEEPL_API_KEY` and `CURATOR_DEEPL_API_PLAN`; do not treat `.env` as a
  general shell script and never execute substitutions or commands from it.
- Add a tracked `.env.example` containing only empty/non-secret placeholders,
  and verify `.env` remains ignored.
- Add an Admin-only readiness/read endpoint and an idempotent on-demand
  translate endpoint for one AI Work Item's current Recommendation list.
- Include available translations in the Review read model without triggering
  external calls during ordinary GET requests.
- Record bounded usage/outcome evidence without storing credentials or raw
  provider headers.

## Out of Scope

- Translating Summary, Description, analysis JSON, or Photo evidence.
- Changing the English candidate selected for approval or Promotion.
- Automatic translation on page load.
- Full historical backfill; owned by `BT-068` after the quality gate.
- Browser presentation; owned by `UI-038`.

## Implementation Steps

1. Amend the controlling API, authentication/configuration, Operation, and UI
   specifications with the decisions above.
2. Add migration-safe cache persistence and concurrency-safe get-or-create.
3. Add secure process-environment/`.env` loading, file-mode validation,
   precedence, fail-closed behavior, and secret-redaction tests.
4. Add the provider adapter, DeepL configuration/readiness, timeout/error
   mapping, quota-safe batching, and secret-redaction tests.
5. Add Admin API/read-model integration and durable usage evidence.
6. Verify cached replay, changed source text, duplicate titles, unavailable
   provider, quota, timeout, malformed response, and concurrent requests.

## Acceptance Criteria

- First request translates only uncached titles and persists non-empty results.
- Later requests and page loads reuse cached translations without contacting
  DeepL.
- English Recommendations and immutable result payloads are byte-for-byte
  unchanged; Review/Promotion behavior is unchanged.
- The API key is absent from database rows, responses, exceptions, request
  logs, Operations, fixtures, screenshots, and committed files.
- Backend starts normally with no `.env`; translation reports Not Configured.
  A valid owner-only `.env` enables it, while an explicit process environment
  value takes precedence. Unsafe `.env` input never executes as shell code.
- Reader/Writer and unauthorized direct requests cannot invoke the provider.
- Provider failure leaves the Review usable and returns a stable, actionable
  error without caching false success.

## Verification

- Repository migration/cache tests and mocked DeepL adapter contract tests.
- Real HTTP authorization/read-model tests with a fake local provider.
- `UI-038` disposable browser acceptance proving one provider call followed by
  cache-only display.
- Complete Backend regression; no test contacts the public DeepL service.

## Risks or Notes

- Short creative Album titles contain metaphor and wordplay. UI copy must say
  the Chinese text is machine translation for comprehension only.
- Never expose the API key to `apps.web`; all provider traffic originates in
  Backend.

## Completion Record

- Added ordered migration `0025_ai_review_translation_cache`, defensive
  repository persistence, cache identity, and canonical schema documentation.
- Added an owner-only repository `.env` loader with process-environment
  precedence, literal parsing, plan validation, and fail-closed diagnostics.
- Added the bounded Backend-only DeepL adapter for Developer/Growth endpoints,
  stable redacted provider errors, and no browser credential exposure.
- Added Admin-only GET/POST Review-translation APIs and cache data in Review
  detail; ordinary reads never invoke DeepL and repeated POSTs are cache-only.
- Preserved immutable Writer recommendations and Review/Promotion state, and
  recorded external cache-miss requests as bounded Operations.
- Verified migration/configuration, fake-provider batching, cached replay,
  unavailable configuration, immutable source data, and real HTTP routing;
  the complete Backend regression passed `804/804` without contacting DeepL.
