---
title: Use the outputs safely
description: Pass LLM-generated outputs to shell and script steps without opening a script injection hole.
sidebar:
  order: 3
---

Changelogs, metadata and reasoning are written by an LLM from commit messages and
diffs, so anyone who can land a commit can influence them. Treat them as untrusted data.

## Never interpolate outputs into `run:` or `script:`

```yaml
# Don't: a quote in the changelog ends the string and the rest runs as shell code
- run: echo '${{ steps.release.outputs.changelogs }}'
```

GitHub substitutes `${{ ... }}` into the script text before the shell parses it.

## Pass them through `env:`

```yaml
- run: jq -r '.customer.es' <<< "$CHANGELOGS"
  env:
    CHANGELOGS: ${{ steps.release.outputs.changelogs }}
```

The value reaches the shell as a variable and is never parsed as code. The same applies
to `actions/github-script`: read `process.env.X`, don't interpolate into `script:`.

## Prefer `changelog_files`

`changelog_files` has the same shape as `changelogs` but holds file paths. Tools that
accept a file then read the changelog without it passing through the shell at all:

```yaml
- run: gh release create "$NEXT_VERSION" --notes-file "$(jq -r '.default.en' <<< "$FILES")"
  env:
    GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
    FILES: ${{ steps.release.outputs.changelog_files }}
    NEXT_VERSION: ${{ steps.release.outputs.next_version }}
```

The files are under `$RUNNER_TEMP`, so only later steps of the same job can read them.
To use one in another job, upload it with `actions/upload-artifact`.

## Rendering changelogs

- Markdown and plain-text changelogs are output unchanged. Escaping them is up to whatever renders them; GitHub already sanitizes release notes.
- `output_format: html` changelogs are meant to be inserted as markup, so the action keeps only structural tags (headings, lists, paragraphs, emphasis, code, links) and `http(s)`, `mailto` and relative links.
- `bump` is always `major`, `minor` or `patch`, and `next_version` is computed by the action, never taken from the model, so both are safe to use as-is.

See [Security model](/llm-release-action/explanation/security-model/) for the full picture.
