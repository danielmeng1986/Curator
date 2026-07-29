# Authentication Specification

## Purpose and scope

This Specification defines device access for Curator's trusted home-LAN model. Curator does not use username/password accounts. It uses approved device tokens for `/api/v1` access.

## Token contract

Clients authenticate with `Authorization: Bearer <token>`. The Backend stores only a token hash, never the plaintext token. Plaintext is displayed once at issuance; the client stores it in protected local configuration.

The persistent `auth_token` record includes at least a token UUID, token hash, device name, permission scope, creation time, expiration time, last-used time, and revocation state. Tokens normally have one-year validity and support renewal, revocation, and reissuance.

## Registration and approval workflow

```mermaid
stateDiagram-v2
    [*] --> RegistrationRequested
    RegistrationRequested --> PendingApproval
    PendingApproval --> Approved: administrator approves
    PendingApproval --> Rejected: administrator rejects
    Approved --> TokenIssued
    TokenIssued --> Active
    Active --> Revoked
    Active --> Expired
    Revoked --> [*]
    Expired --> [*]
    Rejected --> [*]
```

1. A device requests registration.
2. The Backend creates a reviewable event or Issue.
3. An administrator approves or rejects through the server-side Web UI.
4. Approval permits one-time token issuance; the hash is persisted and the plaintext is shown once.
5. The client stores the token locally and uses it on subsequent requests.

### Registration request policy

Curator's current deployment assumes a trusted home LAN and a very small set of trusted devices, initially including only the AI Server. Registration intentionally favors simple, administrator-controlled device access over enterprise identity infrastructure.

A registration request MUST contain only the information needed to identify the requesting device and describe the requested authorization:

| Field | Requirement |
| --- | --- |
| `device_name` | A human-readable identifier for administrator review. |
| `device_id` or `device_fingerprint` | A stable unique identifier used to distinguish the device. `device_name` alone MUST NOT be used as device identity. |
| `requested_role` | The requested role: `reader`, `writer`, or `admin`. |
| `requested_scopes` | Optional requested permissions within the requested role. |
| `registration_proof` | A simple administrator-issued registration secret or one-time registration code. |

The registration proof establishes that the request may be considered; it does not grant access by itself. LAN clients cannot self-register, self-approve, or issue tokens. Automatic approval is not part of the current phase. A local administrator command or loopback-only management endpoint MAY perform the approved administrative action.

Certificates, PKI, mutual TLS, and hardware-backed device identities are intentionally outside the current phase.

## Current authorization model

Roles express the maximum authorization requested by a device, and scopes express the permissions granted to its token. The current role policy is deliberately small:

| Role | Permitted capability |
| --- | --- |
| `admin` | Manage tokens, migrations, restores, backups, and other high-risk administration. |
| `writer` | Perform authorized data writes; cannot perform administrative operations. |
| `reader` | Perform read-only queries. |

`writer` is the highest role normal devices SHOULD request. `admin` privileges are reserved for administrator-controlled devices. The AI Worker normally receives a `writer` token only. Administrator approval is required before any registered device receives a long-lived token, including a token with a reduced role or scope. Scope checking occurs before the protected Service operation runs.

Future versions MAY add richer role or scope management while preserving this role vocabulary and the bearer-token API contract.

## Token renewal and token handling

Tokens have an expiration time; the normal validity period is one year unless an administrator issues a shorter period. A device MAY request renewal before its current token expires. Renewal follows the same administrator-controlled policy as issuance:

1. The device submits a renewal request for its registered identity and current authorization.
2. The Backend records the request for administrator review.
3. An administrator approves or rejects the renewal.
4. After approval, the Backend issues a new token and makes its plaintext available once.
5. Once the new token is valid, the Backend revokes the previous token.

The Backend MUST store only token hashes and MUST reveal a token plaintext only at its initial issuance. It MUST NOT provide an API that retrieves or re-displays an existing token in plaintext. A device that cannot retain its token must use the registration or approved renewal/reissuance workflow; it cannot recover the original value.

The current deployment assumes a trusted LAN. No additional encrypted-token transport mechanism beyond applicable HTTPS requirements is required in this phase.

## Confirmation requirements

The following current-phase actions require administrator approval and no additional confirmation mechanism:

| Action | Required confirmation |
| --- | --- |
| New device registration | Administrator approval. |
| Normal token renewal | Administrator approval. |
| Role elevation | Administrator approval. |

These requirements do not change the general API confirmation contract. They specify the administrative approval required before the associated token-management action may complete.

## Access and error handling

- Missing, invalid, expired, revoked, or malformed credentials are rejected.
- A valid token without the required scope is rejected.
- Authentication failures do not invoke the protected Service operation.
- Token issuance, approval, revocation, and security-relevant failures are recorded as Operations and/or Issues according to their workflow requirements.
- The Backend binds to `127.0.0.1` by default. A LAN bind for the Windows AI Worker is explicit and paired with host-limited firewall rules.

## Future work and transport hardening roadmap

The following stages describe an evolutionary path. Only Stage A is a current requirement. Stage B and Stage C are planning guidance only and are intentionally outside the scope of the first implementation.

### Stage A — Current

- Trusted home LAN.
- Bearer-token authentication.
- Simple administrator approval for device registration, renewal, and role elevation.
- Minimal operational complexity.

### Stage B — Future

- HTTPS everywhere.
- Short-lived access tokens and a refresh workflow.
- Device revocation.
- Improved audit logging.

### Stage C — Long-term

Possible future improvements include device certificates, public-key-based device identity, stronger device authentication, and additional confirmation mechanisms.

QR-code confirmation, PIN-based confirmation, device-to-device approval, and multi-device administrator approval are future-work options only. They MUST NOT complicate the first implementation.

Automatic approval, account systems, and broader network deployment are also not current requirements. Any change to these decisions requires an Architecture/ADR review before implementation.

## Design philosophy

Authentication for Curator remains simple for a single-user trusted environment and avoids unnecessary operational complexity. Current requirements are deliberately separated from future capabilities so stronger mechanisms can be introduced later without changing the overall device-token authentication architecture. The objective is evolutionary architecture rather than premature complexity.
