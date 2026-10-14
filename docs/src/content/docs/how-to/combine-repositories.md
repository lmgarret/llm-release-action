---
title: Release several repositories as one product
description: Use content_override to analyze changes from several repositories, a monorepo or an external tracker in one release.
sidebar:
  order: 11
---

`content_override` replaces git commit detection with Markdown you provide. Use it to:

- combine frontend, backend and mobile repositories into one product release,
- aggregate packages of a monorepo,
- process changes exported from Jira, Linear or another system.

## Format the content

Use a section per source, with change sections under it:

```markdown
## Frontend (v2.1.0)
### Features
- New dashboard with real-time analytics
- Dark mode support

### Fixes
- Fixed login redirect on Safari

## Backend (v3.0.0)
### Breaking Changes
- Removed deprecated /api/v1 endpoints
- Changed auth token format (migration guide: docs/auth-migration.md)

### Features
- Added GraphQL subscriptions
```

## Example workflow

This pulls the release notes of two repositories and writes a combined changelog:

```yaml
name: Product Release
on:
  workflow_dispatch:
    inputs:
      frontend_version:
        description: Frontend version
        required: true
      backend_version:
        description: Backend version
        required: true

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - name: Get Frontend Changelog
        id: frontend
        run: |
          CHANGELOG=$(gh api "repos/myorg/frontend/releases/tags/$VERSION" --jq '.body')
          DELIMITER="EOF_$(openssl rand -hex 16)"
          {
            echo "changelog<<$DELIMITER"
            echo "$CHANGELOG"
            echo "$DELIMITER"
          } >> "$GITHUB_OUTPUT"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          VERSION: ${{ inputs.frontend_version }}

      - name: Get Backend Changelog
        id: backend
        run: |
          CHANGELOG=$(gh api "repos/myorg/backend/releases/tags/$VERSION" --jq '.body')
          DELIMITER="EOF_$(openssl rand -hex 16)"
          {
            echo "changelog<<$DELIMITER"
            echo "$CHANGELOG"
            echo "$DELIMITER"
          } >> "$GITHUB_OUTPUT"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          VERSION: ${{ inputs.backend_version }}

      - uses: lmgarret/llm-release-action@v1
        id: release
        with:
          model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
          current_version: v2024.12.0
          content_override: |
            ## Frontend ${{ inputs.frontend_version }}
            ${{ steps.frontend.outputs.changelog }}

            ## Backend ${{ inputs.backend_version }}
            ${{ steps.backend.outputs.changelog }}
          changelog_config: |
            customer:
              preset: customer
              languages: [en, es]
            internal:
              preset: developer
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: us-east-1

      - name: Print the customer changelog
        run: |
          echo "Version: $NEXT_VERSION"
          cat "$(jq -r '.customer.en' <<< "$FILES")"
        env:
          NEXT_VERSION: ${{ steps.release.outputs.next_version }}
          FILES: ${{ steps.release.outputs.changelog_files }}
```

The random delimiter keeps a release body from ending the multi-line output early.
Interpolating into `with:` is fine: inputs are passed as data, not parsed as shell.

## What to know

- Set `current_version`: there are no tags to detect it from. Without it, `next_version`
  is empty and the release is named `Unreleased`.
- `content_override` replaces git entirely: setting `base_ref`, `tag_pattern`, a
  non-default `head_ref` or `diffs` alongside it fails the run.
- `project_type: auto` falls back to `generic`; set the type explicitly if it matters.
- Large content is split and processed with map/reduce automatically.
- Unlike commits, `content_override` is scanned for prompt injection. HIGH and CRITICAL findings (injection phrases, encoding tricks, content over 500KB) reject the run; MEDIUM findings are logged. The scan is always on. See [Security model](/llm-release-action/explanation/security-model/).
