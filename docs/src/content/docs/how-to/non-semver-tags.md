---
title: Release with non-semver tags
description: Generate changelogs for repositories tagged with timestamps or other non-semver names, or compare from any commit.
sidebar:
  order: 13
---

Set `versioning: none` when your tags aren't semver, such as `demo-202610140930`. The
action then analyzes the range between two refs and generates changelogs, but computes
no next version.

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

      - uses: lmgarret/llm-release-action@v1
        id: release
        with:
          model: anthropic/claude-sonnet-5
          versioning: none
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
    versioning: none
    base_ref: 3f2a1c9
```

`base_ref` also works with `versioning: semver`. The version to bump then comes from
`current_version`, or from the nearest semver tag before `base_ref`.

## What changes with `versioning: none`

- `next_version` is empty. `bump`, `reasoning` and breaking-change detection still work,
  and are still useful to flag a risky release.
- `current_version` holds the base ref.
- Changelogs are titled with `release_name`. By default this is `head_ref` when it is a
  tag, else a tag matching `tag_pattern` on `head_ref`, else `Unreleased`. Set
  `release_name` to choose it yourself, for example the tag your workflow creates next.
- `current_version` can't be set: use `base_ref`.

Without `tag_pattern`, the nearest tag of any name is used. For a first release with no
tags, set `base_ref` to the commit to start from.
