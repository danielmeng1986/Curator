# AI Workspace Acceptance Fixture Contract

## Purpose

This contract defines the disposable Backend fixture consumed by BT-053 and
later UI-011D browser acceptance. It proves workflow behavior; it is not an AI
quality benchmark and never uses production paths, Tokens, databases, or models.

## Fixture contents

- one temporary SQLite database and isolated Archive/snapshot roots;
- tiny synthetic JPEG-signature files with deterministic names and sizes;
- `TEMPORARY` and `NAME_GENERATED` Statuses and no historical
  `workspace_album` input;
- an Open Album-analysis Workspace, one Album, and one or two mock llama.cpp
  configurations with sample count 8;
- fixed Vision v1 and Writer v1 JSON passing the production validators;
- opaque Admin/Writer fixture identities that are never serialized as secrets;
- generic `album_name_analysis` and `metadata_enrichment` Worker kinds.

Every scenario creates a new root and destroys it afterward. Paths supplied to
repositories are below that root. API/read-model assertions reject absolute
Archive paths and never expose claim Tokens.

## Required observable scenarios

The `ai-workspace-workflow` regression group covers:

1. filtered atomic dispatch, one Group, two comparable configurations, immutable
   Manifests, claim-bound evidence transfer, versioned two-stage results, stale
   review rejection, two approvals, one winner, idempotent Promotion, release,
   archive, and redispatch with new identities;
2. wrong-claim denial, unsupported result schema, changed evidence hash, failed
   Work Item, explicit abandonment, and retained degraded history;
3. Rework successor lineage followed by rejection and zero Album mutation; and
4. cross-Worker Album reservation conflict with no partial Group.

UI-011D may start the same disposable Backend and render these durable states,
but must not bypass APIs, rewrite fixture rows, or treat synthetic output as a
real model-quality result.

## Verification commands

Run `python3 apps/backend/tests/run_regression.py ai-workspace-workflow` twice,
then `workflow-readiness` twice, then `all` once. Every run starts from clean
temporary roots and must leave production configuration untouched.
