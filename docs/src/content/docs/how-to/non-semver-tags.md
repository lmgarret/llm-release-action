---
title: Release with non-semver tags
description: Generate changelogs for repositories tagged with timestamps or other non-semver names, or compare from any commit.
sidebar:
  order: 13
---

Set `tag_pattern` when your release tags aren't semver, such as `demo-202610140930`. The
action analyzes the range since the previous matching tag and generates changelogs, but
computes no next version.

## Changelog on each tag push

```yaml
on:
  push:
    tags: ['demo-*']

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: lmgarret/llm-release-action@v2
        id: release
        with:
          model: anthropic/claude-sonnet-5
          tag_pattern: 'demo-*'
          head_ref: ${{ github.ref_name }}
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

The range starts at the nearest `demo-*` tag before `head_ref`. Tags on `head_ref`
itself are skipped, so pushing `demo-202610140930` compares against the previous demo
tag, not against itself. The changelogs are titled with the pushed tag.

## Compare from any commit

`base_ref` takes any tag, SHA or branch and overrides tag detection:

```yaml
    base_ref: 3f2a1c9
```

## What you get without a semver base

- `next_version` is empty and a notice is logged. `bump`, `reasoning` and
  breaking-change detection still work, and are still useful to flag a risky release.
- `current_version` holds the base ref.
- Changelogs are titled with `head_ref` when it is a tag, else a tag matching
  `tag_pattern` on `head_ref`, else `Unreleased`. The `release_name` output holds the
  title used.

To get a `next_version` anyway, set `current_version` to the version to bump from. It
doesn't change the range.

With no matching tag, the whole history of `head_ref` is analyzed and a warning is
emitted. Set `base_ref` to start from a specific commit instead.
