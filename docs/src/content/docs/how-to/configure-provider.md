---
title: Configure your LLM provider
description: Set the model string and credentials for AWS Bedrock, Anthropic, OpenAI, Azure OpenAI or any other LiteLLM provider.
sidebar:
  order: 4
---

The `model` input takes a [LiteLLM model string](https://docs.litellm.ai/docs/providers)
(`<provider>/<model>`). Credentials go in `env:` under the names LiteLLM expects.

## AWS Bedrock

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    AWS_REGION: us-east-1
```

Bedrock keeps your commit data in your AWS account and usually has higher rate limits
than direct APIs. With OIDC, use `aws-actions/configure-aws-credentials` in a previous
step instead of static keys.

## Anthropic

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: anthropic/claude-sonnet-5
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

## OpenAI

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: openai/gpt-4.1
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## Azure OpenAI

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: azure/<deployment-name>
  env:
    AZURE_API_KEY: ${{ secrets.AZURE_API_KEY }}
    AZURE_API_BASE: https://<resource>.openai.azure.com
    AZURE_API_VERSION: 2024-10-21
```

## Other providers

Any provider LiteLLM supports works the same way: use its model prefix and the
environment variables listed on its [LiteLLM provider page](https://docs.litellm.ai/docs/providers).

See [Supported providers and models](/llm-release-action/reference/providers/) for
recommended models, and [Tune models and cost](/llm-release-action/how-to/tune-models-and-cost/)
to use a cheaper model for internal calls.
