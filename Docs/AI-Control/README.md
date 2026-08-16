# Curator AI Control

## Purpose

AI Control owns cross-cutting behavior policy for models executed on Curator
work. It sits above an individual Backend endpoint, Worker implementation, or
Web page and below product/data governance. It defines how Curator versions,
selects, snapshots, transports, validates, evaluates, and audits model
instructions and prompts.

This category exists because model behavior control commonly spans:

- Backend persistence and dispatch snapshots;
- AI Worker prompt composition and provider adaptation;
- schema and deterministic validation;
- Administrator configuration and disclosure;
- evaluation fixtures and reproducibility evidence.

## Task IDs

Tasks use `AIC-<three-digit-sequence>-<short-kebab-case-title>.md`. Status is
`Proposed`, `Ready`, `In Progress`, `Blocked`, `Complete`, or `Superseded`.

An AIC task does not replace component tasks when a change is independently
large. It owns the controlling AI behavior contract and may depend on bounded
BT, UI, or MT implementation tasks.

## Authority boundaries

- An AI Instruction Profile improves model behavior; it is not an authorization
  or integrity boundary.
- Backend workflow, permissions, immutable Evidence Manifests, schemas, and
  deterministic validators remain authoritative.
- Every model run must be reproducible from an immutable Work Item snapshot,
  including resolved instruction/prompt content and hashes—not mutable labels
  alone.
- Model output remains suggestion-only until the existing human Review and
  Promotion workflow accepts it.

## Task index

| Task | Outcome | Status |
| --- | --- | --- |
| [AIC-001](Tasks/AIC-001-versioned-ai-instruction-profile.md) | Versioned Instruction Profile, prompt resolution, immutable run snapshots, and administration | Ready |
