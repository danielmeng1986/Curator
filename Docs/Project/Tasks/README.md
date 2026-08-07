# Curator Project Migration Tasks

This directory plans cross-cutting repository migration work. It complements
`Docs/Backend/Tasks`: Backend tasks implement specified behavior, while these
Migration Tasks move the project into its long-lived layout without changing
the supported Backend contract.

Task IDs use `MT-<three-digit-sequence>` and are executed in dependency order.
The target architecture is the modular monolith defined in
[Backend Architecture](../../Backend/Backend-Architecture.md): Backend owns
database access; Web UI, AI Worker, and tools are API clients.
