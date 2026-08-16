# BT-065 — Retire Promoted Evidence Content

## Task ID

`BT-065` — Status: `Complete`

## Goal

Keep Manifest metadata as durable audit evidence while limiting Admin image
content transfer to the active Review/Promotion period and serving bytes only
from the original Album location.

## Contract

- Evidence metadata and historical availability remain readable after Promotion.
- Image bytes are never copied into the database, Web workspace, or a durable
  thumbnail cache.
- Admin content transfer is allowed before a successful Promotion and rejected
  afterward; failed Promotion attempts do not retire preview access.
- Writer claim-owner access retains its existing lease boundary.
- Missing, changed, unauthorized, or retired content never changes the Manifest.

## Verification

- Service and HTTP tests prove pre-Promotion streaming, post-Promotion denial,
  and continued Manifest/history reads.
- Existing Worker evidence-transfer and AI Workspace regressions pass.

## Completion Record

- Added a Promotion-aware content-transfer guard without changing Manifest or
  historical availability reads.
- Confirmed that image bytes continue to stream only from the original Album
  path with private `no-store` response policy and no schema/storage addition.
- Completed on 2026-08-16; service, real-HTTP API, AI Workspace, Dispatch, and
  simulated Promotion regressions passed.
