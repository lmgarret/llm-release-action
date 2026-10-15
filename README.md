<p align="center">
  <img src="docs/src/assets/logo.svg" alt="LLM Release Action logo" width="96">
</p>

# LLM Release Action

[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/15512/badge)](https://www.bestpractices.dev/projects/15512)

A GitHub Action that uses an LLM to analyze commits, suggest semantic version bumps, and generate changelogs for several audiences and languages.

📖 **Documentation: <https://lmgarret.github.io/llm-release-action/>**
(also as plain text for LLMs: [`llms.txt`](https://lmgarret.github.io/llm-release-action/llms.txt), [`llms-full.txt`](https://lmgarret.github.io/llm-release-action/llms-full.txt))

> **Upgrading from v1?** v2 merges and removes several inputs. See
> [Migrating from v1](https://lmgarret.github.io/llm-release-action/reference/inputs/#migrating-from-v1).

## Features

- **Semantic version analysis**: suggests `major`, `minor` or `patch` from commits and diffs; a major bump needs explicit evidence.
- **Multi-audience changelogs**: developer, customer, executive, marketing, security and ops presets, in any language.
- **Net-state changelogs**: reverted work disappears, related commits become one entry.
- **Any LLM provider** through [LiteLLM](https://docs.litellm.ai/docs/providers): AWS Bedrock, Anthropic, OpenAI, Azure...
- **Project aware**: detects whether you ship a library, API, service or app, and reads your context files to judge what's breaking.

## Quick start

Create a GitHub Release with a generated changelog on every push to `main`:

```yaml
- uses: actions/checkout@v4
  with:
    fetch-depth: 0  # Required: full git history for commit analysis

- uses: lmgarret/llm-release-action@v2
  id: release
  with:
    model: anthropic/claude-sonnet-5
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

- name: Create GitHub Release
  run: gh release create "$NEXT_VERSION" --notes-file "$(jq -r '.default.en' <<< "$FILES")"
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    FILES: ${{ steps.release.outputs.changelog_files }}
    NEXT_VERSION: ${{ steps.release.outputs.next_version }}
```

> **Never interpolate outputs directly into `run:` or `script:`.** Changelogs and
> reasoning are LLM-generated from commits, so anyone who can land a commit can
> influence them. Pass outputs through `env:` as above, or use `changelog_files`.
> See [Use the outputs safely](https://lmgarret.github.io/llm-release-action/how-to/use-outputs-safely/).

## Changelogs for several audiences

```yaml
- uses: lmgarret/llm-release-action@v2
  id: release
  with:
    model: anthropic/claude-sonnet-5
    changelog_config: |
      developer:
        preset: developer
      customer:
        preset: customer
        languages: [en, es, ja]
        generate_title: true
  env:
    ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}

- run: cat "$(jq -r '.customer.es' <<< "$FILES")"
  env:
    FILES: ${{ steps.release.outputs.changelog_files }}
```

## Learn more

- [Your first release](https://lmgarret.github.io/llm-release-action/tutorials/first-release/): step-by-step tutorial
- [How-to guides](https://lmgarret.github.io/llm-release-action/how-to/create-github-release/): PR comments, app store notes, multi-repo releases, project context, diff analysis...
- [Inputs](https://lmgarret.github.io/llm-release-action/reference/inputs/) and [outputs](https://lmgarret.github.io/llm-release-action/reference/outputs/) reference
- [How it works](https://lmgarret.github.io/llm-release-action/explanation/how-it-works/) and [security model](https://lmgarret.github.io/llm-release-action/explanation/security-model/)

The documentation source is in [`docs/`](docs/). Run it locally with `cd docs && npm install && npm run dev`.

## License

MIT
