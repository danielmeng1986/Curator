# Database Domain Overview

> Documentation status: Current
> Owner: Database
> Last verified: 2026-08-11

```mermaid
flowchart LR
    AUTH["Authentication"]
    CATALOG["Asset Catalog"]
    OPS["Operations / Repair / Recovery"]
    DISPATCH["Work Dispatch"]
    AI["AI Workspace / Review"]
    MIGRATION["Schema Migration"]
    HISTORICAL["Historical Workspace"]

    AUTH -->|"actor identity"| OPS
    AUTH -->|"Admin / Worker identity"| DISPATCH
    AUTH -->|"review and submission actor"| AI
    CATALOG -->|"Album and filesystem truth"| OPS
    CATALOG -->|"Album eligibility"| DISPATCH
    DISPATCH -->|"Group and Work Item"| AI
    AI -->|"approved name Promotion"| CATALOG
    AI -->|"audit Operations"| OPS
    MIGRATION -->|"versioned schema"| CATALOG
    MIGRATION -->|"versioned schema"| DISPATCH
    MIGRATION -->|"versioned schema"| AI
    HISTORICAL -.->|"retained provenance only"| CATALOG
```

Solid arrows show active data/workflow dependencies. The dotted Historical
edge is provenance only; it does not expose an active Workspace client surface.
