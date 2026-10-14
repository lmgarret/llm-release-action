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
| `model` | *required* | LiteLLM model string, e.g. `anthropic/claude-sonnet-5` or `bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0`. Default for every phase. |
| `model_analysis` | `model` | Model for Phase 1 semantic analysis (and diff analysis). |
| `model_changelog` | `model` | Model for Phase 2 changelog generation. |
| `model_profile` | `model` | Model for project type detection. A small model is enough. |
| `validation_model` | `model` | Model for LLM prompt injection validation. |

## Model parameters

See [Model parameters](/llm-release-action/explanation/model-parameters/).

| Input | Default | Description |
|-------|---------|-------------|
| `max_tokens` | `4000` | Max tokens in each LLM response, including internal calls. On models that think, thinking tokens count against it. |
| `timeout` | `120` | Request timeout in seconds. |
| `temperature` | *unset* | Sent only when set. Many current models (Sonnet 5+, Opus 4.7+, Haiku 5.5) reject it. |
| `thinking` | *unset* | Sent only when set. `adaptive` sends `{"type": "adaptive"}`, `off` sends `{"type": "disabled"}`. Some models reject `off`. |
| `extra_llm_params` | *unset* | JSON object merged into every LLM call, last, so it overrides the inputs above. E.g. `{"reasoning_effort": "low"}`. |

## Version range

| Input | Default | Description |
|-------|---------|-------------|
| `current_version` | latest semver tag | Semver version to bump from. Also the ref to compare from when `base_ref` is not set. Required if the repository has no semver tag and `versioning` is `semver`. |
| `head_ref` | `HEAD` | Ref to compare to. |
| `base_ref` | *detected* | Any git ref (tag, SHA, branch) to compare from. With `semver`, the version still comes from `current_version` or the nearest semver tag before it. |
| `tag_pattern` | *unset* | Glob matching release tags, e.g. `demo-*`. Without `base_ref`, the range starts at the nearest matching tag before `head_ref`. |
| `versioning` | `semver` | `semver` computes `next_version` from the bump. `none` skips version calculation, for tags that aren't semver. See [Release with non-semver tags](/llm-release-action/how-to/non-semver-tags/). |
| `release_name` | *derived* | Name of the release in changelogs. Defaults to `next_version`; with `versioning: none`, to `head_ref` if it is a tag, else a tag matching `tag_pattern` on `head_ref`, else `Unreleased`. |
| `max_commits` | `50` | Number of most recent commits included in full. Older ones are summarized. |
| `dry_run` | `false` | Only marks the run as a dry run in the log. The action never creates tags or releases itself; your later steps do. |
| `debug` | `false` | Verbose logging, including prompts and responses. |

## Analysis

| Input | Default | Description |
|-------|---------|-------------|
| `project_type` | `auto` | `auto`, `library`, `api`, `service`, `app` or `generic`. Decides what counts as breaking. See [Project types](/llm-release-action/reference/project-types/). |
| `include_diffs` | `**/openapi*.yaml,**/migrations/**,**/*.proto` | Comma-separated globs of files whose raw diffs are added to the prompt. |
| `context_files` | *unset* | Comma-separated gitignore-style patterns (negation supported) of project documentation to give the model. See [Provide project context](/llm-release-action/how-to/provide-project-context/). |
| `context_max_tokens` | `800` | Token budget for context. Larger content is summarized with map/reduce. |
| `analyze_diffs` | `false` | Extract structured changes from each file diff with an LLM. See [Analyze file diffs](/llm-release-action/how-to/analyze-diffs/). |
| `diff_exclude_patterns` | [lock, vendor, generated files](/llm-release-action/reference/default-patterns/#diff-exclusions) | Comma-separated gitignore-style patterns excluded from diff analysis. Replaces the defaults. |
| `diff_max_files` | `50` | Max files analyzed. Higher-signal files are kept first. |
| `diff_max_total_lines` | `5000` | Max total diff lines analyzed. |

## Changelogs and content

| Input | Default | Description |
|-------|---------|-------------|
| `changelog_config` | *unset* | YAML map of audiences. See [Changelog config](/llm-release-action/reference/changelog-config/). Unset: one `default` audience in English, using the `developer` preset (`customer` for `app` projects). |
| `content_override` | *unset* | Markdown to analyze instead of git commits. See [Release several repositories](/llm-release-action/how-to/combine-repositories/). |
| `validate_injections` | `pattern` | Prompt injection scanning of `content_override`: `pattern` (regex), `both` (regex + LLM), `llm` (LLM only), `none`. |
