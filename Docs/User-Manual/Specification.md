# Curator Application User Manual Specification

> Documentation status: Approved
> Owner: Project documentation
> Last verified: 2026-08-11

## Purpose

This Specification controls user-facing operating manuals for runnable
applications under `apps/`. It makes manuals predictable across applications,
roles, languages, milestones, and release Tags while keeping developer tooling
out of ordinary user instructions.

## Audience and authority

Manuals explain how to operate supported applications. They do not redefine
Architecture, API, security, destructive-action, recovery, or workflow rules.
When a manual conflicts with an approved Specification or active application,
the conflict is documentation drift and the manual must be corrected.

The manual audience includes:

- operators installing, starting, stopping, migrating, backing up, and
  troubleshooting a Server application;
- end users operating Client applications;
- Administrators performing authentication, authorization, review, recovery,
  and high-risk actions;
- role-limited users who need to understand both available actions and expected denial.

## Application inclusion policy

### Included

Every supported runnable application under `apps/` receives a manual when its
surface is usable. Current applications are:

| Application | Category | Manual requirement |
| --- | --- | --- |
| `apps.backend` | Server | Server operations manual |
| `apps.web` | Client | Client overview plus Reader, Writer, and Admin guidance |

An application directory that contains only a future foundation, tests, or no
supported entry point is listed as `Not yet documented` rather than described
as usable.

### Excluded by default

- scripts under `tools/`;
- tests, fixtures, benchmark helpers, one-off migration analysis, and developer utilities;
- raw REST endpoint reference intended for implementers;
- historical/retired applications and unsupported launchers.

### Strong-association exception

A command outside the ordinary UI may appear only when it is necessary to
operate an included application and no supported in-application replacement
exists. The manual must explain why it is required and keep it inside the owning
application workflow, not create a general Tools chapter.

Current examples:

- `python3 -m apps.backend auth bootstrap-code` for first-Admin initialization;
- `python3 -m apps.backend.migrations` for explicit Backend schema maintenance;
- the guarded historical Workspace archive command only when upgrading a
  database that actually requires it.

## Information architecture

Manuals are grouped by runtime responsibility first:

```text
Docs/User-Manual/
├── README.md
├── Specification.md
├── en/
│   ├── server/
│   │   └── apps-backend.md
│   └── client/
│       └── apps-web/
│           ├── README.md
│           ├── reader.md
│           ├── writer.md
│           └── administrator.md
└── zh-CN/
    ├── server/
    │   └── apps-backend.md
    └── client/
        └── apps-web/
            ├── README.md
            ├── reader.md
            ├── writer.md
            └── administrator.md
```

Future Server and Client applications follow the same pattern. Slugs and file
layout must match across locales so parity can be checked mechanically.

## Required Server manual structure

Each Server manual contains, in this order where applicable:

1. purpose, supported status, and relationship to Clients;
2. prerequisites and supported runtime assumptions;
3. configuration and managed paths, with secret-handling warnings;
4. first-time database initialization/migration;
5. start, health verification, normal stop, and restart;
6. first-Administrator bootstrap boundary;
7. authentication/LAN exposure and least-privilege guidance;
8. backup, Snapshot, Restore, logs, and recovery operations;
9. maintenance windows and upgrade procedure;
10. troubleshooting by observable symptom;
11. high-risk and irreversible-action warnings;
12. verification checklist and links to Client role manuals.

Server instructions must distinguish ordinary startup from explicit maintenance
commands. They must never suggest testing against a live database or bypassing
the Backend with direct SQL.

## Required Client manual structure

Each Client application overview contains:

1. purpose and what the Client intentionally does not do;
2. how to open/connect and where credentials come from;
3. navigation and shared concepts;
4. role/capability matrix;
5. shared feedback, error, cancellation, and retry behavior;
6. role-manual links;
7. safety and troubleshooting.

Each role manual contains:

1. role purpose and prerequisites;
2. first login/connection;
3. visible navigation and permitted workflows;
4. step-by-step happy paths;
5. expected denials and escalation path;
6. review/confirmation requirements;
7. role-specific security and data-disclosure boundaries;
8. troubleshooting and verification checklist.

## Current apps.web role requirements

### Reader

- connect using an approved Reader Token;
- browse permitted Album/entity/Operation summaries;
- understand read-only UI and direct-write denial;
- understand that sensitive recovery context is withheld.

### Writer

- request/receive approved Writer access;
- manage permitted permanent entities and Album relationships;
- preview and execute Import;
- review Issues and perform only permitted Repair decisions;
- understand Admin-only Quarantine, authorization, backup/restore, dispatch,
  AI review/Promotion, and suppression boundaries.

### Administrator

- generate the first Bootstrap Code in the terminal and complete loopback UI initialization;
- store the one-time issued Admin Token and acknowledge it safely;
- review device registration, approve/reject, renew/elevate, and revoke Tokens;
- preserve the final usable Admin Token;
- administer Issues, Repair suppression, Quarantine and item Restore;
- administer Backup/Snapshot cleanup and protected database Restore;
- configure AI models, create Workspaces, dispatch Albums, review/rework/reject,
  promote one Album name, release Groups, and close/archive Workspaces;
- understand previews, typed confirmation, stale/replay rejection, Snapshots,
  session invalidation, partial failure, audit evidence, and irreversible boundaries.

## Writing rules

- Lead with the user outcome, then numbered steps.
- Use UI labels exactly as rendered and commands exactly as supported.
- State the required role before every restricted workflow.
- Put warnings before the action that creates risk, not after it.
- Distinguish Preview, Execute, Cancel, Retry, Restore, Release, Archive, and Purge.
- Never promise success before the application verifies the durable/filesystem outcome.
- Do not expose example real Tokens, paths, credentials, or private asset names.
- Link to technical Specifications only as optional deeper context.
- Screenshots are optional and must never be the sole source of a step or label.

## Multilingual contract

- English (`en`) and Simplified Chinese (`zh-CN`) are mandatory default locales.
- Both locales have identical files, headings, workflow coverage, warnings, and link targets.
- English is the terminology reference when a stable code/API term has no safe translation.
- Product labels, enum/state names, commands, paths, confirmation phrases, and
  error codes remain verbatim; explanatory prose is translated.
- A change is incomplete if only one mandatory locale is updated.
- Translation must preserve safety strength; it may not soften “must”, “never”,
  authorization, destructive, backup, or recovery language.

## Version and release maintenance

Manual maintenance is repeatable, not a one-time task. Refresh is required:

- at a documented application milestone;
- before creating a release Tag;
- after a supported route/navigation/role/workflow changes;
- after authentication, destructive action, backup/restore, recovery, or
  disclosure behavior changes;
- when an application is added, retired, or changes Server/Client status.

Each refresh records:

- target application commit or release Tag;
- supported applications and entry points;
- route/navigation and role-capability inventory;
- completed workflow acceptance evidence;
- English/Chinese parity result;
- known limitations and intentionally excluded tools.

The manual describes the tagged/current supported surface, not unmerged plans.

## Verification gates

A manual release passes only when:

- every documented application has a supported entry point;
- every documented command succeeds in a disposable/safe environment;
- UI labels/routes and role visibility match browser acceptance;
- high-risk workflows match Backend/UI Specifications;
- English and Chinese file/heading/link parity passes;
- relative links resolve;
- no credential, private path, production data, or sensitive diagnostic is embedded;
- known blocked features are labeled unavailable rather than described as usable.

## Change ownership

- Product/runtime gaps discovered while writing manuals become BT, UI, or MT tasks.
- Manual structure, language, navigation, and refresh automation use DOC tasks.
- Database operator instructions must follow DBDOC/BT schema authority.
- A release documentation refresh may update manuals without reopening this
  Specification unless the manual contract itself changes.

