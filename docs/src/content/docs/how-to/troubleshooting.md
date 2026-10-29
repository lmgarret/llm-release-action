---
title: Troubleshoot common errors
description: Fixes for missing tags or versions, rate limits, authentication errors, invalid bumps, empty or hallucinated changelogs.
sidebar:
  order: 14
---

To log the full prompts and responses, enable GitHub's debug logging: re-run the job
with **Enable debug logging**, or set the `ACTIONS_STEP_DEBUG` secret or variable to `true`.

## No tag found, or `next_version` is empty

With no tag matching `tag_pattern` before `head_ref`, the whole history is analyzed and
the action warns. If the base tag isn't semver, `next_version` is empty. Pass
`current_version: v1.0.0` (or `v0.0.0` for a first release) to get one, or set
`tag_pattern` to match your release tags. See
[Release with non-semver tags](/llm-release-action/how-to/non-semver-tags/).

## Rate limit errors (429)

The action retries with exponential backoff. If limits persist:

- use a model with higher rate limits,
- narrow `diffs` or lower `diff_max_lines` to send less data,
- consider AWS Bedrock, which usually has higher limits than direct APIs.

## Authentication errors (401/403)

Check the environment variables for your provider:

- **AWS Bedrock**: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`
- **OpenAI**: `OPENAI_API_KEY`
- **Anthropic**: `ANTHROPIC_API_KEY`, or the federation variables. A failed federation
  exchange always reads `Authentication failed`; the reason is in the Claude Console's
  [authentication history](https://platform.claude.com/settings/workload-identity-federation?tab=history).
  `match_subject_prefix` there means the rule's subject isn't the token's `sub`: see
  [the subject format](/llm-release-action/how-to/configure-provider/#without-an-api-key).
  Also check that the rule's audience is `https://api.anthropic.com`, with no trailing slash.

Secrets aren't passed to workflows triggered by pull requests from forks.

## A parameter is rejected

For example `` `temperature` is deprecated for this model ``. The action sends
`llm_params` as configured; remove the one the model rejects. See
[Tune models and cost](/llm-release-action/how-to/tune-models-and-cost/#fix-a-rejected-parameter).

## "LLM returned empty response"

The model spent its `max_tokens` on thinking. Raise `max_tokens` or lower the reasoning effort.

## Invalid bump response

The model didn't return a valid bump. This is rare and usually comes from a very short
history or unusual commit formats. Add signal with `diffs` or `context_files`, or try a
more capable `model`.

## The changelog is empty

Check that:

- there are commits between the base ref (the `current_version` output) and `head_ref`,
- `actions/checkout` uses `fetch-depth: 0`,
- commit messages are meaningful (not just "update" or "fix").

## "No changes in this release" or irrelevant content

An audience's filters can exclude every change. The action then skips the LLM call and
returns "No changes in this release" rather than letting the model invent content.
Check that the audience's `sections` cover the categories you expect and that
`exclude_categories` doesn't filter everything. The `developer` preset includes all sections.
