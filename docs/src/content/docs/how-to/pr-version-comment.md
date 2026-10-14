---
title: Comment the suggested version on pull requests
description: Run the action on every pull request and post or update a comment with the suggested bump and reasoning.
sidebar:
  order: 2
---

Save as `.github/workflows/pr-version.yml`:

```yaml
name: PR Version Check
on:
  pull_request:
    types: [opened, synchronize]

jobs:
  check:
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: lmgarret/llm-release-action@v1
        id: semver
        with:
          model: anthropic/claude-sonnet-5
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      # Pass outputs through env, never ${{ }} inside script: the reasoning
      # is LLM-generated from this PR's commits and could break out of a JS string.
      - name: Comment on PR
        uses: actions/github-script@v7
        env:
          BUMP: ${{ steps.semver.outputs.bump }}
          CURRENT_VERSION: ${{ steps.semver.outputs.current_version }}
          NEXT_VERSION: ${{ steps.semver.outputs.next_version }}
          REASONING: ${{ steps.semver.outputs.reasoning }}
        with:
          script: |
            const { BUMP, CURRENT_VERSION, NEXT_VERSION, REASONING } = process.env;

            const body = `## Version Analysis

            | Current | Bump | Next |
            |---------|------|------|
            | ${CURRENT_VERSION} | **${BUMP}** | ${NEXT_VERSION} |

            ### Reasoning
            ${REASONING}
            `;

            const { data: comments } = await github.rest.issues.listComments({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
            });
            const existing = comments.find(c =>
              c.user.type === 'Bot' && c.body.includes('## Version Analysis')
            );

            if (existing) {
              await github.rest.issues.updateComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                comment_id: existing.id,
                body,
              });
            } else {
              await github.rest.issues.createComment({
                owner: context.repo.owner,
                repo: context.repo.repo,
                issue_number: context.issue.number,
                body,
              });
            }
```

The comment is updated in place on each push to the pull request instead of piling up.

:::caution
Pull requests from forks don't get your repository secrets, so the LLM call fails for
them. Don't switch to `pull_request_target` to work around it: that runs with secrets
on code the fork controls.
:::
