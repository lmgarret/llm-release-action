---
title: Inputs
description: Every input of lmgarret/llm-release-action with its default and meaning.
sidebar:
  order: 1
---

All inputs are strings, as with every GitHub Action. Only `model` is required.

## Models

| Input | Default | Description |
|-------|---------|-------------|
| `model` | *required* | LiteLLM model string, e.g. `anthropic/claude-sonnet-5` or `bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0`. Used for consolidation, analysis and changelog writing. |
| `fast_model` | `model` | Model for the cheap internal calls: project type detection, context file summarization and diff extraction. A small model is enough. |

## Model parameters

See [Model parameters](/llm-release-action/explanation/model-parameters/).

| Input | Default | Description |
|-------|---------|-------------|
| `llm_params` | *unset* | JSON object merged into every LLM call, passed through as-is. E.g. `{"temperature": 0.2}`, `{"thinking": {"type": "adaptive"}}`, `{"reasoning_effort": "low"}`. |
| `max_tokens` | `4000` | Max tokens in each LLM response, including internal calls. On models that think, thinking tokens count against it. |
| `timeout` | `120` | Request timeout in seconds. |

## Version range

| Input | Default | Description |
|-------|---------|-------------|
| `head_ref` | `HEAD` | Ref to compare to. |
| `base_ref` | *detected* | Any git ref (tag, SHA, branch) to compare from. Unset: the nearest tag matching `tag_pattern` strictly before `head_ref` (tags on `head_ref` itself are skipped). With no such tag, the whole history of `head_ref` is analyzed and a warning is emitted. An explicit `base_ref` that doesn't exist is an error. |
| `tag_pattern` | `v[0-9]*.[0-9]*.[0-9]*` | Glob matching release tags (as in `git describe --match`), e.g. `demo-*`. |
| `current_version` | *version of the base tag* | Semver version to bump from. Overrides the version read from the base tag; never changes the range. Set it with `content_override`, for a first release (`v0.0.0`), or when tags aren't semver but you still want `next_version`. |

`next_version` is computed when `current_version` is set or the base ref is a semver tag
(`v1.2.3`, `1.2.3`, `v1.2.3-rc.1`). Otherwise it is empty and `release_name` is the tag on
`head_ref`, or `Unreleased`. See [Release with non-semver tags](/llm-release-action/how-to/non-semver-tags/).

## Analysis

| Input | Default | Description |
|-------|---------|-------------|
| `project_type` | `auto` | `auto`, `library`, `api`, `service`, `app` or `generic`. Decides what counts as breaking. See [Project types](/llm-release-action/reference/project-types/). |
| `context_files` | `/README.md` | Comma-separated gitignore-style patterns (negation supported) of project documentation to give the model. A leading `/` anchors a pattern to the repository root; without it, `README.md` also matches nested READMEs. Empty string disables it. See [Provide project context](/llm-release-action/how-to/provide-project-context/). |
| `context_max_tokens` | `800` | Token budget for context. Larger content is summarized with map/reduce. |
| `diffs` | `**/openapi*.yaml,**/migrations/**,**/*.proto` | Comma-separated gitignore-style patterns (negation supported) of files whose diffs are analyzed. Empty string disables diff analysis. See [Analyze file diffs](/llm-release-action/how-to/analyze-diffs/). |
| `diff_max_lines` | `5000` | Budget of changed lines across all analyzed diffs. Higher-signal files are kept first. |

## Changelogs and content

| Input | Default | Description |
|-------|---------|-------------|
| `changelog_config` | *unset* | YAML map of audiences. See [Changelog config](/llm-release-action/reference/changelog-config/). Unset: one `default` audience in English, using the `developer` preset. |
| `content_override` | *unset* | Markdown to analyze instead of git commits. Can't be combined with `base_ref`, `tag_pattern`, `head_ref` or `diffs`. Always scanned for prompt injection. See [Release several repositories](/llm-release-action/how-to/combine-repositories/). |

## Migrating from v1

| v1 input | Replacement |
|----------|-------------|
| `model_analysis`, `model_changelog` | `model`. All main work runs on it. |
| `model_profile` | `fast_model`, which also handles context summarization and diff extraction. |
| `validation_model`, `validate_injections` | None. `content_override` is always pattern-scanned; the optional LLM check is gone. |
| `temperature` | `llm_params: '{"temperature": 0.2}'` |
| `thinking: adaptive` / `off` | `llm_params: '{"thinking": {"type": "adaptive"}}'` / `'{"thinking": {"type": "disabled"}}'` |
| `extra_llm_params` | `llm_params` |
| `include_diffs`, `analyze_diffs`, `diff_exclude_patterns`, `diff_max_files` | `diffs`. Matching diffs are always analyzed; exclude files with `!` patterns. |
| `diff_max_total_lines` | `diff_max_lines` |
| `versioning: none` | None. Without `current_version` or a semver base tag, `next_version` is empty. |
| `max_commits` | None. Fixed at 50. |
| `dry_run` | None. It only logged a message; the action never creates releases. |
| `debug` | None. Use GitHub's debug logging: re-run the job with **Enable debug logging**, or set the `ACTIONS_STEP_DEBUG` secret or variable to `true`. |

Other behavior changes:

- `current_version` no longer sets the start of the range. Use `base_ref` for that.
- `tag_pattern` defaults to `v[0-9]*.[0-9]*.[0-9]*`. Set it if your release tags have another shape.
- Without a matching tag, the whole history is analyzed instead of failing.
- `context_files` defaults to `/README.md` (the root README). Set it to an empty string to keep the old behavior.
- `project_type: app` no longer switches the default changelog to the `customer` preset.
  For a user-facing default changelog, set `changelog_config: "default: {preset: customer}"`.
- Diffs matching `diffs` now always reach the analysis. In v1, raw diffs were dropped
  whenever consolidation succeeded.
