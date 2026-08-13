# Curator UI Design and Delivery Documentation

> Documentation status: Current
> Owner: UI
> Last verified: 2026-08-13

## Purpose

This directory describes how Curator's Backend capabilities are organized into
usable Web workflows. It is neither an operator manual nor an alternative
Backend contract. User instructions belong under `Docs/User-Manual`; durable
data, authorization, and workflow invariants remain owned by Backend
Specifications.

Its scope is `apps.web` information architecture, interaction characteristics,
feature workflows, delivery tasks, and verification evidence.

## Authority and document roles

| Document | Role |
| --- | --- |
| [UI Specification](Specification.md) | Approved normative requirements for complete, discoverable, interruption-safe browser workflows. |
| [Foundation and Navigation](Foundation-and-Navigation.md) | Current application shell, routes, roles, visual character, and shared interface patterns. |
| [Data Interaction Rules](Data-Interaction-Rules.md) | Current field ownership, relationship editing, labels, and data-presentation rules. |
| [Feature descriptions](Features/) | Current behavior and design characteristics of major UI areas; these must conform to the Specification and Backend contracts. |
| [Verification Strategy](Verification-Strategy.md) | Test-layer responsibilities, fixture isolation, evidence handling, and release verification. |
| [Workflow Readiness Matrix](Workflow-Readiness-Matrix.md) | Living map from Backend evidence to shipped UI outcomes and current readiness. |
| [UI Tasks](Tasks/README.md) | Proposed, active, blocked, completed, and superseded units of UI delivery work. Completed tasks are historical execution records. |
| [Audits](Audits/) | Dated historical assessments. They preserve findings at the audit date and do not describe current readiness unless explicitly stated. |

When documents disagree, use the question-specific precedence in
[Documentation Governance](../Documentation-Governance.md): current code and
schema establish implemented fact, Specifications establish approved contract,
the Readiness Matrix establishes current evidence, and dated audits/tasks
preserve history.

## Feature descriptions

| Feature | Contents |
| --- | --- |
| [Entity Management](Features/Entity-Management.md) | Albums, Models, Studios, Statuses, relationships, and the Photo ownership boundary. |
| [Direct Album Import](Features/Direct-Album-Import.md) | Resumable folder discovery, reviewed import, mapping, conflict handling, and results. |
| [AI Collection Workspace](Features/AI-Collection-Workspace.md) | Dispatch, Worker results, human Review, Promotion, Group release, and historical Workspace boundary. |

## Reading order

1. Read the [UI Specification](Specification.md) for normative workflow rules.
2. Read Foundation and Data Interaction Rules for shared UI characteristics.
3. Read the relevant Feature description for current user-facing behavior.
4. Consult the Readiness Matrix for accepted evidence and remaining gaps.
5. Use Tasks for delivery history and Audits only for dated analysis context.

## Maintenance triggers

- A route, role-visible entry, shared component, or LAN/browser boundary change
  updates Foundation and Navigation.
- A field, relationship, label, or ownership change updates Data Interaction
  Rules and its affected Feature description.
- A workflow-state, persistence, recovery, or confirmation change updates the
  Specification when normative, the Feature description when behavioral, and
  the Readiness Matrix when evidence changes.
- A new gap receives a UI task; a documentation-structure or authority change
  receives a DOC task.
- User-facing operating steps are updated separately in every mandatory manual
  locale after the behavior is accepted.
