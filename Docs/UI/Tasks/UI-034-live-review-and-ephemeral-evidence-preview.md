# UI-034 — Live Review and Ephemeral Evidence Preview

## Task ID

`UI-034` — Status: `Complete`

## Goal

Keep AI Review Queue/Detail truthful while Workers and reviewers change state,
and let an Admin inspect Manifest images without growing the application
workspace or retaining image bytes after the Review/Promotion period.

## Interaction Contract

- Queue and Detail poll authoritative state every five seconds while visible,
  pause in hidden tabs, avoid overlapping requests, back off after failures,
  preserve active editing focus/drafts, and stop on route exit.
- Evidence cards load only near the visible gallery, with at most three content
  requests in flight.
- Authenticated content becomes browser-memory Blob URLs; client-side thumbnails
  and full-image previews create no durable file or database copy.
- Object URLs are revoked on rerender, route exit, replacement, or preview close.
- A successfully promoted item shows retained Manifest metadata and discloses
  that image preview has ended.

## Out of Scope

- Permanent thumbnails, image database blobs, Service Worker/offline caches,
  framework migration, image editing, or bulk image export.

## Verification

- UI contract tests cover polling, bounded loading, Blob URLs, and cleanup.
- Real-browser acceptance proves automatic Queue state change, lazy preview,
  full-image display, and post-Promotion retirement.

## Completion Record

- Added five-second visibility-aware Queue/Detail polling with edit-focus
  protection, overlap prevention, route cleanup, and bounded failure backoff.
- Added authenticated `no-store` Blob reads, viewport-driven loading, a
  three-request concurrency ceiling, browser-memory thumbnail generation,
  temporary full-image preview, and Object URL cleanup.
- Added a post-Promotion retained-Manifest/retired-preview state.
- Completed on 2026-08-16; focused API/UI contracts and real-browser Queue,
  thumbnail, full-preview, Promotion-retirement, Dispatch, and simulated
  Promotion journeys passed.
