---
title: Your first release
description: Add the action to a repository, check its suggestion with a dry run, then publish a GitHub Release with a generated changelog.
sidebar:
  order: 1
---

In this tutorial you add LLM Release Action to a repository, preview the version it
suggests, and publish a GitHub Release whose notes it wrote. It takes about ten minutes.

You need:

- A GitHub repository with a few commits, ideally in [Conventional Commits](https://www.conventionalcommits.org/) style (`feat:`, `fix:`...). Any style works, but conventional commits give the model clearer signals.
- An API key for an LLM provider. This tutorial uses Anthropic; see [Configure your LLM provider](/llm-release-action/how-to/configure-provider/) for Bedrock, OpenAI and others.

## 1. Add your API key as a secret

In your repository, open **Settings → Secrets and variables → Actions** and add a
repository secret named `ANTHROPIC_API_KEY` with your key.

## 2. Tag a starting version

The action compares `HEAD` with the latest semver tag. If your repository has no tag
yet, create one on an older commit so the release covers only the commits after it:

```bash
git tag v0.1.0 <commit-sha>
git push origin v0.1.0
```

:::tip
No tags and don't want to create one? Skip this step: the whole history is analyzed.
Pass `current_version: v0.0.0` to get a suggested version. See
[Handle a first release or pre-releases](/llm-release-action/how-to/first-release-and-prereleases/).
:::

## 3. Add the workflow

Create `.github/workflows/release.yml`:

```yaml
name: Release
on:
  workflow_dispatch:
    inputs:
      dry_run:
        description: Show the suggested version without releasing
        type: boolean
        default: true

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # The action needs the full git history

      - uses: lmgarret/llm-release-action@v2
        id: release
        with:
          model: anthropic/claude-sonnet-5
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

      - name: Show the result
        env:
          BUMP: ${{ steps.release.outputs.bump }}
          NEXT_VERSION: ${{ steps.release.outputs.next_version }}
          FILES: ${{ steps.release.outputs.changelog_files }}
        run: |
          echo "## $NEXT_VERSION ($BUMP)" >> "$GITHUB_STEP_SUMMARY"
          cat "$(jq -r '.default.en' <<< "$FILES")" >> "$GITHUB_STEP_SUMMARY"

      - name: Create GitHub Release
        if: ${{ !inputs.dry_run }}
        env:
          GH_TOKEN: ${{ github.token }}
          NEXT_VERSION: ${{ steps.release.outputs.next_version }}
          FILES: ${{ steps.release.outputs.changelog_files }}
        run: |
          gh release create "$NEXT_VERSION" \
            --title "$NEXT_VERSION" \
            --notes-file "$(jq -r '.default.en' <<< "$FILES")"
```

Commit and push it to your default branch.

Notice that the outputs reach the shell through `env:`, never as `${{ ... }}` inside
`run:`. The changelog is text an LLM generated from your commits, so it must be
treated as untrusted. [Use the outputs safely](/llm-release-action/how-to/use-outputs-safely/) explains why.

## 4. Do a dry run

Open the **Actions** tab, pick **Release**, and click **Run workflow** with *dry run*
checked. When it finishes, open the run: the summary shows the suggested version, the
bump type and the changelog.

If the suggestion looks wrong, the `reasoning` output and the step log explain what the
model based it on.

## 5. Release

Run the workflow again with *dry run* unchecked. The last step creates the tag and the
GitHub Release, with the generated changelog as release notes. Open **Releases** in your
repository to see it.

## Next steps

- Write changelogs for several audiences and languages: [Generate multi-audience changelogs](/llm-release-action/how-to/multi-audience-changelogs/).
- Post the suggested bump on every pull request: [Comment the suggested version on pull requests](/llm-release-action/how-to/pr-version-comment/).
- Improve breaking change detection: [Provide project context](/llm-release-action/how-to/provide-project-context/).
- Understand what happened under the hood: [How it works](/llm-release-action/explanation/how-it-works/).
