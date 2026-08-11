# Application Manual Release Refresh Record

> Copy this file for each application milestone or before creating a release Tag.
> Store the completed record with the release evidence; do not overwrite this template.

## Target

- Milestone/release:
- Candidate commit or Tag:
- Review date:
- Reviewer:

## Supported application inventory

| Application | Category | Supported entry point | Status/change |
| --- | --- | --- | --- |
| `apps.backend` | Server | `python3 -m apps.backend` | |
| `apps.web` | Client | Served by `apps.backend` from `apps/web/static` | |

## Change review

- [ ] Application entry points and supported runtime assumptions were rechecked.
- [ ] Routes, navigation labels, role/scopes, and disclosure behavior were rechecked.
- [ ] Authentication and first-Administrator instructions were rechecked.
- [ ] Preview/Execute, destructive, backup/Restore, and failure behavior were rechecked.
- [ ] Ready workflows were added; blocked/retired workflows are not presented as usable.
- [ ] English and Simplified Chinese files were updated together.
- [ ] Tools remain excluded except for a documented strong-association exception.

## Acceptance evidence

- User-manual gate command/result:
- Safe command checks performed:
- Browser acceptance suites/results:
- Related BT/UI/MT/DOC tasks:

## Known limitations and exclusions

- Known limitations:
- Intentionally excluded tools/applications:
- Follow-up task IDs:

## Approval

- [ ] Documentation matches the candidate commit/Tag.
- [ ] No Token, credential, private path, production data, or sensitive diagnostic is embedded.
- [ ] Release owner accepts documented limitations.

Decision: `Pass / Fail`  
Approved by/date:
