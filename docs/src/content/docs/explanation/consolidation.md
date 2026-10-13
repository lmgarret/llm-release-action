---
title: Changelog consolidation
description: Why changelogs show the net state of a release rather than its commit history, with examples.
sidebar:
  order: 2
---

A changelog should say what changed between two releases, not retell how the work went.
If a feature was added and then reverted, listing both is confusing: for the reader,
nothing changed.

So the action reads changes in order and keeps their net effect:

- **added then reverted** → excluded (net zero),
- **added then improved or fixed** → only the final state,
- **related changes** → one entry.

## Example: reverted feature

Commits:

```
1. feat: Add Stripe payment
2. fix: Fix payment validation
3. feat: Add dark mode
4. revert: Revert Stripe payment
```

Changelog:

```markdown
## Features
- Dark mode support
```

Stripe is gone: it was reverted, so its net impact is zero. The fix to it disappears too.

## Example: consolidated work

Commits:

```
1. feat: Add OAuth login
2. fix: Fix OAuth token refresh
3. feat: Add OAuth scope support
```

Changelog:

```markdown
## Features
- OAuth 2.0 authentication with token refresh and scope support
```

The fix isn't listed as a bug fix: from the reader's point of view, the bug never
shipped. The three commits describe one feature.

## Consequences

- Counts in `stats` are counts of consolidated changes, not commits.
- A consolidated change keeps every commit and author in its `commits` and `authors` fields.
