---
title: Supported providers and models
description: LLM providers usable through LiteLLM, example model strings and recommended models for changelog quality.
sidebar:
  order: 7
---

Any provider [LiteLLM supports](https://docs.litellm.ai/docs/providers) works. Examples:

| Provider | Model strings | Credentials |
|----------|---------------|-------------|
| AWS Bedrock | `bedrock/us.anthropic.claude-sonnet-5-v1:0`, `bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0`, `bedrock/us.amazon.nova-pro-v1:0` | `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION` |
| Anthropic | `anthropic/claude-sonnet-5`, `anthropic/claude-opus-5`, `anthropic/claude-sonnet-4-5-20250929` | `ANTHROPIC_API_KEY` |
| OpenAI | `openai/gpt-4.1`, `openai/gpt-4o`, `openai/gpt-4o-mini` | `OPENAI_API_KEY` |
| Azure OpenAI | `azure/<deployment-name>` | `AZURE_API_KEY`, `AZURE_API_BASE`, `AZURE_API_VERSION` |

## Model recommendations

For the best changelogs, use Sonnet-class or equivalent models:

| Provider | Recommended | Notes |
|----------|-------------|-------|
| AWS Bedrock | `claude-sonnet-5`, `claude-sonnet-4-5-*`, `nova-pro-v1` | Best instruction following |
| Anthropic | `claude-sonnet-5`, `claude-opus-5`, `claude-sonnet-4-5-*` | Excellent formatting |
| OpenAI | `gpt-4.1`, `gpt-4o` | Good quality output |

Smaller models (Haiku 4.5, Nova Lite, GPT-4.1-mini) are faster and cheaper but may:

- ignore formatting instructions (e.g. use bold when asked not to),
- produce redundant title/description pairs,
- miss nuanced audience transformations.

Use a capable model for `model`, and a cheaper one for `fast_model` if cost matters.

## Parameter compatibility

Parameters set in `llm_params` that some models reject:

| Parameter | Known incompatibilities |
|-----------|------------------------|
| `"temperature"` | Rejected by Sonnet 5 and later, Opus 4.7 and later, Haiku 5.5, Fable, Mythos (`` `temperature` is deprecated for this model ``) |
| `"thinking": {"type": "disabled"}` | Rejected by some models, e.g. Sonnet 5.5, Opus 5.5, Fable. Lower the effort instead. |
