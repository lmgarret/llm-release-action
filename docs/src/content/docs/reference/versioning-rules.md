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

The version to bump from is `current_version` when set, else the base tag: the nearest
tag matching `tag_pattern` before `head_ref`, if it is semver (`v1.2.3`, `1.2.3`,
`v1.2.3-rc.1`). Without either, `next_version` is empty and a notice is logged; `bump`
and the changelogs are still produced.

With no matching tag, the whole history is analyzed. Pass `current_version: v0.0.0` for
a first release, which then gets `v0.1.0` or `v1.0.0`.
