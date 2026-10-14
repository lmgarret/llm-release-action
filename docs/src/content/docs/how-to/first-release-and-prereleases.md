---
title: Handle a first release or pre-releases
description: Release a repository with no tags yet, and understand how bumps apply to alpha and beta versions.
sidebar:
  order: 12
---

## First release (no tags)

Without a release tag, the action analyzes the whole history of `head_ref` and warns
that no tag was found. There is no version to bump from, so `next_version` is empty. Pass
`current_version` to get one:

```yaml
- uses: lmgarret/llm-release-action@v2
  with:
    model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
    current_version: v0.0.0
```

The action then suggests `v0.1.0` or `v1.0.0` depending on the changes. If your tags aren't semver, see
[Release with non-semver tags](/llm-release-action/how-to/non-semver-tags/).

## Pre-releases

When the current version is a pre-release such as `v1.0.0-alpha.1`:

- a **patch** bump increments the pre-release number: `v1.0.0-alpha.1` → `v1.0.0-alpha.2`
- a **minor** or **major** bump promotes to a stable release: `v1.0.0-alpha.1` → `v1.1.0` or `v2.0.0`

If you maintain a floating major tag (such as `v1`), don't move it on pre-releases.
