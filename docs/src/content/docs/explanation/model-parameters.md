---
title: Model parameters
description: Why the action passes llm_params through unchanged instead of adapting them per model, and what that means for thinking models.
sidebar:
  order: 5
---

The action passes model parameters through exactly as you configure them in
`llm_params`. It doesn't keep a list of what each model accepts.

## Why pass-through

Providers change accepted parameters with almost every model generation: `temperature`
became deprecated on recent Anthropic models, `thinking` gained new modes, some models
refuse to disable thinking. A built-in compatibility table would always be out of date,
and silently dropping or rewriting a parameter would hide what was actually sent.
Dedicated inputs per parameter would have the same problem, so there is one JSON input
instead.

With pass-through:

- a new model or parameter works the day it ships,
- a parameter the model rejects fails with the provider's own error naming it, and the fix is in your workflow inputs.

## What is sent

By default only `model`, `max_tokens` and `timeout`. `llm_params` adds any other
provider parameter, merged into every call (analysis, changelogs and the `fast_model`
calls alike). For example:

- `{"temperature": 0.2}`
- `{"thinking": {"type": "adaptive"}}` or `{"thinking": {"type": "disabled"}}`
- `{"reasoning_effort": "low"}`

`reasoning_effort` is translated by LiteLLM into Anthropic's adaptive thinking plus
`output_config.effort`. It also sets `thinking`, so combining both keys sends
conflicting values.

## Thinking and `max_tokens`

On models that think, thinking tokens come out of `max_tokens`. When the cap is too small
for thinking plus the answer, the model returns empty content and the call fails with
"LLM returned empty response". The default of 4000 suits most runs.

See [Tune models and cost](/llm-release-action/how-to/tune-models-and-cost/) for
configurations, and [Parameter compatibility](/llm-release-action/reference/providers/#parameter-compatibility)
for known rejections.
