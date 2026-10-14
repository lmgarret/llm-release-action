---
title: Tune models and cost
description: Use a cheaper model for internal calls, set reasoning effort or other model parameters, raise max_tokens, and monitor token usage.
sidebar:
  order: 13
---

## Use a cheaper model for internal calls

`model` does the main work: consolidation, analysis and changelog writing. `fast_model`
handles the cheap internal calls: project type detection, context file summarization and
diff extraction. It defaults to `model`.

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0
    fast_model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
```

Changelog quality depends most on `model`: smaller models tend to ignore formatting
instructions. See [model recommendations](/llm-release-action/reference/providers/#model-recommendations).

## Set reasoning effort

Pass any provider parameter with `llm_params`, a JSON object merged into every call.
LiteLLM translates `reasoning_effort` into Anthropic's adaptive thinking plus
`output_config.effort` (`low`, `medium`, `high`, `xhigh`, `max`):

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: anthropic/claude-sonnet-5-5
    fast_model: anthropic/claude-haiku-5-5
    llm_params: '{"reasoning_effort": "low"}'
```

Other examples: `'{"thinking": {"type": "adaptive"}}'`, `'{"temperature": 0.2}'`.
Don't set both `reasoning_effort` and `thinking`: both end up in `thinking`, and the
request carries conflicting values.

## Fix "LLM returned empty response"

On models that think, thinking tokens count against `max_tokens`. If the cap is too small
for thinking plus the answer, the model returns empty content. Raise it:

```yaml
max_tokens: 8000
```

## Fix a rejected parameter

The action sends `llm_params` exactly as configured, so a parameter the model doesn't
accept fails with the provider's error naming it. Remove it from `llm_params`. For
example, current Anthropic models reject `temperature`.
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

- Use a small model for `fast_model`.
- Narrow `diffs`, lower `diff_max_lines`, or set `diffs: ""` to skip diff analysis.
- Set `project_type` explicitly to skip the detection call.
