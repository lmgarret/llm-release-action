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
- uses: lmgarret/llm-release-action@v2
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
- uses: lmgarret/llm-release-action@v2
  with:
    model: anthropic/claude-sonnet-5
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

### Without an API key

With [Workload Identity Federation](https://platform.claude.com/docs/en/manage-claude/wif-providers/github-actions),
the action trades the job's GitHub OIDC token for a short-lived Anthropic token, so no
key is stored in GitHub. In the Claude Console, under **Workload identity**, connect a
GitHub Actions workload: it creates a service account and a federation rule. Set the
rule's audience to `https://api.anthropic.com`, with no trailing slash.

The rule's subject must equal the `sub` claim of the job's token, which depends on the
repository and the job:

- A job with `environment: release` gets `...:environment:release`; other jobs get
  `...:ref:refs/heads/main` (or `:pull_request` for pull requests).
- With immutable subjects, it starts with `repo:<owner>@<owner_id>/<repo>@<repo_id>`
  rather than `repo:<owner>/<repo>`. `gh api repos/<owner>/<repo>/actions/oidc/customization/sub`
  shows which one your repository uses, in `sub_claim_prefix`.

For example: `repo:octo-org@9919/octo-repo@1296269:environment:release`.

```yaml
permissions:
  contents: read
  id-token: write # lets the job request an OIDC token

steps:
  - uses: lmgarret/llm-release-action@v2
    with:
      model: anthropic/claude-sonnet-5
    env:
      ANTHROPIC_FEDERATION_RULE_ID: fdrl_...
      ANTHROPIC_ORGANIZATION_ID: 00000000-0000-0000-0000-000000000000
      ANTHROPIC_SERVICE_ACCOUNT_ID: svac_...
      ANTHROPIC_WORKSPACE_ID: wrkspc_... # only when the rule covers several workspaces
```

These IDs aren't secrets. Leave `ANTHROPIC_API_KEY` unset: the action stops with an
error when both are set. The Anthropic token stays inside the action's process, and is
renewed with a fresh GitHub token before it expires. Outside GitHub Actions, set
`ANTHROPIC_IDENTITY_TOKEN_FILE` or `ANTHROPIC_IDENTITY_TOKEN` to your provider's OIDC token.

## OpenAI

```yaml
- uses: lmgarret/llm-release-action@v2
  with:
    model: openai/gpt-4.1
  env:
    OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
```

## Azure OpenAI

```yaml
- uses: lmgarret/llm-release-action@v2
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
