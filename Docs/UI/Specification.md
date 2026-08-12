# Curator Web UI Specification

> Status: Approved  
> Scope: `apps.web` user experience and browser-workflow behavior  
> Backend authority: Backend Specifications remain authoritative for data,
> authorization, security invariants, and durable side effects.

## 1. Purpose

This Specification controls how Curator exposes Backend capabilities as usable,
safe, and recoverable browser workflows. A UI feature is not complete merely
because every Backend endpoint has a button. It is complete only when an
eligible user can discover the workflow, understand the current state, perform
the next valid action, leave safely, return later, and verify the outcome.

Curator is currently a personal application, but it must not depend on the
operator remembering hidden commands, transient dialogs, implementation
details, or an undocumented sequence of actions.

## 2. Authority and relationship to other documents

- Backend Specifications define what operations and state transitions are
  valid. The UI must not weaken or duplicate Backend authorization.
- This Specification defines the user-facing orchestration of those operations.
- Files `01`–`06` define shared and feature-specific UI requirements and must
  conform to this Specification.
- The [Workflow Readiness Matrix](Workflow-Readiness-Matrix.md) records coverage
  and evidence. Task completion alone does not establish workflow readiness.
- User manuals explain the shipped behavior. They do not compensate for an
  undiscoverable or incomplete UI.

When an intended UI workflow cannot be implemented safely with the available
Backend contract, the UI task is **Blocked by Specification** or by Backend work;
the client must not invent an unsafe workaround.

## 3. UI workflow model

Every material workflow must define the following as one coherent contract:

| Concern | Required answer |
| --- | --- |
| Entry | Where can each eligible role discover and start the workflow? |
| Preconditions | What role, connection, data, proof, or system state is required? |
| State | What user-visible states exist before, during, and after execution? |
| Next action | What is the single clear next action in each non-terminal state? |
| Persistence | Which state survives modal close, navigation, refresh, browser restart, Backend restart, or delayed human action? |
| Recovery | How does the same browser resume, retry, cancel, or escalate? |
| Completion | What visible evidence proves the durable outcome? |
| Failure | What remains unchanged, what input is retained, and how can the user continue? |
| Security | Which values may be displayed, stored locally, sent, logged, or never disclosed? |
| Acceptance | Which real-browser journey proves the happy path and interruption paths? |

The specification for a workflow must cover its complete user journey, not only
the page owned by one Backend resource.

## 4. Interaction requirements

### 4.1 Discoverability

- Every available primary workflow has a stable entry in navigation, the page
  action area, a relevant empty state, or the persistent top bar.
- A transient modal, toast, or one-time success screen must never be the only
  way to continue a non-terminal workflow.
- Labels describe the user's outcome or next action, such as **Request device
  access**, **Check registration status**, or **Review import**, rather than an
  endpoint or internal record type.
- Role-hidden actions must have a documented escalation path where the user can
  reasonably need them. The Backend remains authoritative if a hidden action is
  invoked directly.

### 4.2 State visibility and truthful feedback

- The UI distinguishes idle, editing, validating, submitting, waiting,
  succeeded, partially succeeded, failed, rejected, expired, and cancelled
  states where they apply.
- A loading state identifies the operation and prevents accidental duplicate
  submission without making the rest of the application appear frozen.
- Success is shown only after the Backend confirms the authoritative outcome.
- Pending and partial outcomes are not presented as success.
- Feedback names what happened, the affected scope, and the next useful action.
  Material operations link to their Operation, Snapshot, Issue, or result when
  that evidence exists.

### 4.3 Continuity and recovery

- Closing a modal must not cancel a workflow unless the UI says so and the user
  explicitly confirms cancellation.
- Every non-terminal durable or locally recoverable workflow keeps a stable
  resume entry until it reaches a terminal state or the user deliberately
  abandons it.
- Navigation and refresh preserve safe progress. Browser restart and Backend
  restart behavior must be specified explicitly.
- Locally held secrets or candidate credentials may remain browser-profile
  bound; the UI must explain that clearing site data, using another profile, or
  losing the profile can make recovery impossible.
- When recovery is impossible, the UI must say why and offer a safe restart or
  administrator-assisted resolution. It must not silently create duplicates.

### 4.4 Delayed and multi-actor workflows

Workflows involving another person, browser, process, or delayed Backend job
must be designed as asynchronous workflows even if they often complete quickly.

- The requester can leave and later resume from a stable entry.
- The UI shows who or what must act next and whether the state is still current.
- Status checking is idempotent and safe to repeat.
- Approved, rejected, expired, revoked, stale, and missing states have distinct
  explanations and next actions.
- The UI must not rely on a dialog remaining open while an Administrator or
  background process completes work.

### 4.5 Errors, retry, and idempotency

- Validation errors preserve entered values and identify fields plus a concise
  page-level summary when submission is blocked.
- Network failure is distinguished from authorization failure, validation,
  conflict, stale state, and verified Backend failure.
- Retry is offered only when repeating the request is safe. Execution requests
  use Backend preview identities, idempotency, or replay protection as required
  by their controlling contract.
- Rejection, cancellation, stale state, repeated action, and insufficient scope
  must not cause an unintended durable or filesystem mutation.

### 4.6 Safe confirmation

- Confirmation strength is proportional to risk. Ordinary saves need no
  theatrical confirmation; destructive, filesystem-changing, bulk, release,
  archive, purge, and database-restore actions require reviewed scope and the
  confirmation specified by the Backend workflow.
- Confirmation text names the action and consequences. A generic **OK** is not
  sufficient for a high-risk action.
- Cancel is always safe and never represented as a failure.

### 4.7 Accessibility and comprehensibility

- State, error, permission, and selection are not communicated by color alone.
- Controls have stable accessible names; keyboard focus moves into dialogs and
  returns to the invoking control when they close.
- The visible next action remains understandable without consulting source
  code, API documentation, or a terminal, except where an approved local-host
  security boundary explicitly requires a command.
- Empty states explain both why content is absent and what the user can do next.

## 5. Browser persistence and application upgrades

- Browser-local state has a named owner, version-tolerant schema, validation,
  and an explicit removal point.
- Compatible older local state is migrated or normalized when read. Invalid
  state fails safely and does not expose secrets.
- Authentication and in-progress workflow state must not be placed in URL query
  parameters, fragments, analytics, console output, or retained diagnostics.
- Web entry documents and executable UI assets must use cache behavior or
  content versioning that prevents an older client from continuing silently
  after a Backend upgrade.
- Browser acceptance must include refresh after deployment for changes that
  alter persisted state, routing, authentication, or recovery behavior.

## 6. Authentication reference workflow

Authentication is the first normative example of this Specification.

### 6.1 First Administrator

The UI must identify an uninitialized installation, explain the local-host
boundary, guide the operator to the supported Bootstrap Code action, accept it
once, disclose the resulting Admin Token once, require acknowledgement, and
then show the authenticated device state. Wrong, expired, replayed, and remote
bootstrap attempts remain truthful and side-effect free.

### 6.2 Reader and Writer enrollment

1. An unauthenticated browser has a discoverable **Request device access** entry.
2. It generates and retains its candidate Device Token and enrollment proof
   inside that browser profile, then submits only the permitted request data.
3. After submission, the persistent top bar shows **Check registration status**.
   Closing the waiting dialog, navigating, refreshing, restarting the browser,
   restarting the Backend, or delayed Admin action must not remove that entry.
4. The Admin sees the request in **Devices and Tokens** and may approve or
   reject it under the Backend authorization contract.
5. Repeated status checks are safe. Approval validates the locally held Token,
   stores it as the active device credential, clears pending enrollment state,
   updates role-visible navigation, and reports success.
6. Rejection, expiry, missing local material, cleared site data, or a different
   browser profile explains the recovery boundary and never fabricates a Token.

The Registration Proof enables submission only. The candidate Device Token and
enrollment proof never cross browser profiles through UI recovery. Administrator
approval cannot reconstruct locally lost plaintext credentials.

### 6.3 Normal connection lifecycle

The persistent top bar always exposes one truthful connection state: initialize,
request access, check registration, connect/reconnect, or current device and
role. Renewal, revocation, expiry, and insufficient scope must lead to a clear
state and next action without erasing unrelated local work.

## 7. Workflow specification requirements

Before implementing or materially changing a UI workflow, its controlling UI
document or task must include:

1. roles, entry points, preconditions, and Backend dependencies;
2. a state/transition table including terminal and interruption states;
3. persistence and recovery behavior across modal close, navigation, refresh,
   browser restart, Backend restart, and delayed completion where applicable;
4. success, partial-success, empty, authorization, validation, conflict,
   network, stale, replay, and cancellation behavior as applicable;
5. secret/disclosure and destructive-action boundaries;
6. desktop browser acceptance scenarios and required durable zero-side-effect
   assertions.

Wireframes may supplement these requirements but cannot replace state and
recovery definitions.

## 8. Acceptance and definition of done

A UI workflow is Ready only when:

- the complete happy path can be performed from discoverable UI entries;
- all supported roles see the correct capability and denial boundaries;
- at least the applicable modal-close, navigation, refresh, browser-restart,
  Backend-restart, delayed-action, retry, and cancellation paths are verified;
- real-browser evidence proves visible state and the Backend/API layer proves
  durable state and zero unintended side effects;
- upgrade/cache behavior is covered when client assets or local state change;
- diagnostics and retained artifacts contain no prohibited credentials;
- English and Simplified Chinese manuals describe the shipped workflow and its
  recovery boundaries using current labels.

Manual success during one uninterrupted session is useful exploratory evidence,
but it is not sufficient acceptance for a persistent workflow.
