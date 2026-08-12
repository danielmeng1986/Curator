# UI-[NNN] — [Short task title]

## Task ID

`UI-[NNN]` — Status: `[Proposed | Ready | In Progress | Blocked | Complete | Superseded]`

## Title

`[Concise action-oriented title]`

## Related Specification(s)

- `[UI or Backend specification and controlling section]`

## Goal

[One coherent user-visible or verification outcome.]

## Scope

- [Included pages, states, roles, or test boundary.]

## Workflow Contract

- Entry and preconditions: [stable discovery point, eligible roles, and required state.]
- States and next actions: [idle/pending/success/failure/terminal states and transitions.]
- Persistence and recovery: [modal close, navigation, refresh, browser restart,
  Backend restart, delayed action, and client upgrade behavior as applicable.]
- Completion evidence: [visible and durable evidence that proves the outcome.]
- Failure safety: [retained input, retry/cancel path, and zero-side-effect boundary.]

## Out of Scope

- [Excluded adjacent behavior or follow-up work.]

## Dependencies

- `[Task/specification/fixture]` — [Reason], or `None`.

## Implementation Steps

1. [Small reviewable step.]
2. [Small reviewable step.]
3. [Focused automated verification.]

## Acceptance Criteria

- [Observable successful behavior.]
- [Observable rejection/failure behavior and side-effect rule.]
- [Role, disclosure, accessibility, or compatibility boundary.]
- [Applicable interruption and resume paths are observable and verified.]

## Verification

- [Named browser, contract, or focused test.]
- [Relevant Backend workflow and regression gates.]
- [Refresh/restart/upgrade or delayed-action evidence where applicable.]

## Risks or Notes

- [Specification ambiguity, safety/recovery concern, or `None`.]
