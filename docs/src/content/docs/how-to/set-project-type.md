---
title: Set the project type
description: Choose or auto-detect whether the project is a library, API, service or app, which decides what counts as a breaking change.
sidebar:
  order: 10
---

By default (`project_type: auto`), a small LLM call classifies the project from its
README and file layout. It runs on `fast_model`, so a cheap model is enough:

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0
    fast_model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
    project_type: auto
```

If you know the type, set it to skip detection:

```yaml
project_type: app  # or library, api, service, generic
```

The type actually used is in the `project_type` output. Detection falls back to
`generic` when it isn't confident, and always with `content_override`.

The type doesn't change the default changelog, which always uses the `developer`
preset. For a user-facing changelog, for example for an app, set:

```yaml
changelog_config: "default: {preset: customer}"
```

See [Project types](/llm-release-action/reference/project-types/) for what each type
treats as breaking, and [Breaking changes](/llm-release-action/explanation/breaking-changes/)
for why it matters.
