---
title: Breaking changes
description: Why major bumps need explicit evidence, why what counts as breaking depends on the project type, and how context files help.
sidebar:
  order: 3
---

A major bump tells every consumer they may have to change something before upgrading.
A false one makes people delay safe upgrades; a missed one breaks them. The action is
built to avoid both, but leans towards caution about *raising* a major.

## Conservative by default

A major bump needs explicit evidence: a `BREAKING CHANGE:` footer, a `!` after the
commit type, or a diff that removes an API endpoint, a field or a database column.
A commit that merely sounds big ("rewrite the auth module") doesn't qualify on its own.
See [Versioning rules](/llm-release-action/reference/versioning-rules/).

## Breaking for whom?

Whether a change is breaking depends on who consumes the project. A large database
migration in an Android app breaks nobody: the app migrates its own data on update. The
same migration on a database shared with other services breaks every one of them.

That's why the action first decides the [project type](/llm-release-action/reference/project-types/)
(library, API, service, app) and judges changes from that consumer's point of view. The
common rule: a change is breaking only if an existing consumer has to act.
Irreversibility alone (no rollback or downgrade) isn't enough.

## Project context

Without context, the model has to guess what's public. It may flag the removal of an
internal helper as breaking, or miss that an undocumented function is in fact used by
clients.

[Context files](/llm-release-action/how-to/provide-project-context/) state it explicitly:
which APIs and endpoints are public, which code is internal, and the project's
conventions. The model treats them as reference data, not instructions: explicit evidence
in the changes still outranks them.

## Diffs as evidence

Commit messages can understate a change. Diffs of API specs and migrations show what
actually changed. Files matching [`diffs`](/llm-release-action/how-to/analyze-diffs/)
are analyzed for what was added, removed and modified, and the result goes into the
analysis next to the commits.
