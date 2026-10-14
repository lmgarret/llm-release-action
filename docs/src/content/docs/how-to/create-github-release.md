---
title: Create a GitHub Release on push
description: Publish a tagged GitHub Release with an LLM-written changelog every time you push to the main branch.
sidebar:
  order: 1
---

Save as `.github/workflows/release.yml`:

```yaml
name: Release
on:
  push:
    branches: [main]
  workflow_dispatch:

jobs:
  release:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0  # Required: full git history for commit analysis

      - uses: lmgarret/llm-release-action@v2
        id: release
        with:
          model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
        env:
          AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
          AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          AWS_REGION: us-east-1

      - name: Create GitHub Release
        run: |
          gh release create "$NEXT_VERSION" \
            --title "$NEXT_VERSION" \
            --notes-file "$(jq -r '.default.en' <<< "$FILES")"
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          FILES: ${{ steps.release.outputs.changelog_files }}
          NEXT_VERSION: ${{ steps.release.outputs.next_version }}
```

Without a [`changelog_config`](/llm-release-action/reference/changelog-config/), the action
writes one English changelog under the `default` audience, so its file is at
`.default.en` in `changelog_files`.

## Variations

- **Different provider**: swap the `model` and credentials, see [Configure your LLM provider](/llm-release-action/how-to/configure-provider/).
- **Keep a floating major tag** (`v1` pointing to the latest `v1.x.y`): after the release, run `git tag -f "${NEXT_VERSION%%.*}" && git push origin "${NEXT_VERSION%%.*}" --force`. Skip it for pre-releases.
- **Release notes in another job**: `changelog_files` live under `$RUNNER_TEMP` and are only readable within the same job. Upload the file with `actions/upload-artifact` and download it in the other job.
- **Manual approval**: trigger on `workflow_dispatch` only and add a boolean workflow input that skips the release step, as in [Your first release](/llm-release-action/tutorials/first-release/).
