---
title: Versioning rules
description: What leads to a major, minor or patch bump, and how bumps apply to pre-release versions.
sidebar:
  order: 5
---

## Bump levels

**MAJOR** requires explicit evidence, interpreted per [project type](/llm-release-action/reference/project-types/):

- a commit body contains `BREAKING CHANGE:`,
- a commit type ends with `!` (`feat!:`, `fix!:`),
- an API endpoint or field is removed in an OpenAPI diff,
- a database column is dropped in a migration diff.

**MINOR**: new functionality:

- commits of type `feat:`,
- new API endpoints or fields.

**PATCH**: everything else:

- bug fixes (`fix:`),
- documentation, tests, chores,
- internal improvements.

## Version computation

`next_version` is computed by the action from `current_version` and `bump`. The model
only chooses the bump, which must be exactly `major`, `minor` or `patch`.

| Current | Bump | Next |
|---------|------|------|
| `v1.2.3` | patch | `v1.2.4` |
| `v1.2.3` | minor | `v1.3.0` |
| `v1.2.3` | major | `v2.0.0` |
| `v1.0.0-alpha.1` | patch | `v1.0.0-alpha.2` |
| `v1.0.0-alpha.1` | minor | `v1.1.0` |
| `v1.0.0-alpha.1` | major | `v2.0.0` |

## Current version detection

Without `current_version`, the latest semver tag is used. With no semver tag the run
fails; pass `current_version` (e.g. `v0.0.0` for a first release, which then gets
`v0.1.0` or `v1.0.0`).
