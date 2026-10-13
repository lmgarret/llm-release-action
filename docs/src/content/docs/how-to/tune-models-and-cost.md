---
title: Tune models and cost
description: Use different models per phase, set reasoning effort or thinking, raise max_tokens, and monitor token usage.
sidebar:
  order: 13
---

## Use a different model per phase

`model` is the default. Override it per phase:

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
    model_analysis: bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0   # Phase 1: version and change extraction
    model_changelog: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0   # Phase 2: changelog writing
    model_profile: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0     # project type detection
    validation_model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0  # LLM injection checks
```

Changelog quality depends most on `model_changelog`: smaller models tend to ignore
formatting instructions. See [model recommendations](/llm-release-action/reference/providers/#model-recommendations).

## Set reasoning effort

Pass any provider parameter with `extra_llm_params`. LiteLLM translates
`reasoning_effort` into Anthropic's adaptive thinking plus `output_config.effort`
(`low`, `medium`, `high`, `xhigh`, `max`):

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: anthropic/claude-sonnet-5-5
    model_analysis: anthropic/claude-haiku-5-5
    extra_llm_params: '{"reasoning_effort": "low"}'
```

Don't combine it with the `thinking` input: both set `thinking`, and the request carries
conflicting values.

## Fix "LLM returned empty response"

On models that think, thinking tokens count against `max_tokens`. If the cap is too small
for thinking plus the answer, the model returns empty content. Raise it:

```yaml
max_tokens: 8000
```

## Fix a rejected parameter

The action sends parameters exactly as configured, so a parameter the model doesn't
accept fails with the provider's error naming it. Remove it from the workflow. For
example, current Anthropic models reject `temperature`; leave it unset for them.
See [Model parameters](/llm-release-action/explanation/model-parameters/).

## Monitor usage

The `usage` output has calls, tokens and latency per model:

```yaml
- name: Log usage
  run: jq . <<< "$USAGE"
  env:
    USAGE: ${{ steps.release.outputs.usage }}
```

## Reduce cost

- Lower `max_commits` (default 50): older commits are summarized instead of sent in full.
- Keep `analyze_diffs` off, or lower `diff_max_files`.
- Use a small model for `model_analysis`, `model_profile` and `validation_model`.
- Set `project_type` explicitly to skip the detection call.
