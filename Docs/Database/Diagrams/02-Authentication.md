# Authentication ER Model

> Documentation status: Current
> Owner: Database
> Last verified: 2026-08-11

```mermaid
erDiagram
    DEVICE_REGISTRATION {
        TEXT uuid PK
        TEXT device_identity
        TEXT requested_role
        TEXT approved_role
        TEXT status
    }
    AUTH_TOKEN {
        TEXT uuid PK
        TEXT registration_uuid FK
        TEXT token_hash
        TEXT scopes
        TEXT expires_at
        TEXT revoked_at
    }
    TOKEN_RENEWAL_REQUEST {
        TEXT uuid PK
        TEXT registration_uuid FK
        TEXT previous_token_uuid FK
        TEXT status
    }
    ADMIN_BOOTSTRAP_CODE {
        TEXT uuid PK
        TEXT code_hash
        TEXT expires_at
        TEXT used_at
        TEXT locked_at
        INTEGER failed_attempts
    }

    DEVICE_REGISTRATION ||--o{ AUTH_TOKEN : receives
    DEVICE_REGISTRATION ||--o{ TOKEN_RENEWAL_REQUEST : requests
    AUTH_TOKEN ||--o{ TOKEN_RENEWAL_REQUEST : previous_token
```

Bootstrap Code consumption creates the first approved Admin identity but is not
a permanent FK relationship. Plaintext Tokens and Bootstrap Codes are never
stored. Last-Admin safety, role transitions, expiry, and one-time disclosure are
Service/API rules backed by tests rather than simple ER cardinality.
