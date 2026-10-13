---
title: Troubleshoot common errors
description: Fixes for missing tags, rate limits, authentication errors, invalid bumps, empty or hallucinated changelogs.
sidebar:
  order: 14
---

Set `debug: true` to log the full prompts and responses.

## "No semver tags found"

The repository has no tag like `v1.2.3`, or uses non-semver tags. Pass
`current_version: v1.0.0` (or `v0.0.0` for a first release).

## Rate limit errors (429)

The action retries with exponential backoff. If limits persist:

- use a model with higher rate limits,
- lower `max_commits` to send less data,
- consider AWS Bedrock, which usually has higher limits than direct APIs.

## Authentication errors (401/403)

Check the environment variables for your provider:

- **AWS Bedrock**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- **OpenAI**: `OPENAI_API_KEY`
- **Anthropic**: `ANTHROPIC_API_KEY`

Secrets aren't passed to workflows triggered by pull requests from forks.

## A parameter is rejected

For example `` `temperature` is deprecated for this model ``. The action sends parameters
as configured; remove the one the model rejects. See
[Tune models and cost](/llm-release-action/how-to/tune-models-and-cost/#fix-a-rejected-parameter).

## "LLM returned empty response"

The model spent its `max_tokens` on thinking. Raise `max_tokens` or lower the reasoning effort.

## Invalid bump response

The model didn't return a valid bump. This is rare and usually comes from a very short
history or unusual commit formats. Add signal with `include_diffs` or
`context_files`, or try a more capable `model_analysis`.

## The changelog is empty

Check that:

- there are commits between `current_version` and `head_ref`,
- `actions/checkout` uses `fetch-depth: 0`,
- commit messages are meaningful (not just "update" or "fix").

## "No changes in this release" or irrelevant content

An audience's filters can exclude every change. The action then skips the LLM call and
returns "No changes in this release" rather than letting the model invent content.
Check that the audience's `sections` cover the categories you expect and that
`exclude_categories` doesn't filter everything. The `developer` preset includes all sections.
