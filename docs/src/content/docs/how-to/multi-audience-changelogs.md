---
title: Generate multi-audience changelogs
description: Write separate changelogs for developers, customers, executives and others, in several languages, with titles, summaries and highlights.
sidebar:
  order: 5
---

Define one entry per audience in `changelog_config`. Each key becomes a key of the
`changelogs`, `changelog_files` and `metadata` outputs.

## Start from presets

```yaml
- uses: lmgarret/llm-release-action@v2
  id: release
  with:
    model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
    changelog_config: |
      developer:
        preset: developer
        languages: [en]
      customer:
        preset: customer
        emojis: true
        languages: [en, es, ja]
      executive:
        preset: executive
        max_items_per_section: 5
        languages: [en]
  env:
    AWS_ACCESS_KEY_ID: ${{ secrets.AWS_ACCESS_KEY_ID }}
    AWS_SECRET_ACCESS_KEY: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
    AWS_REGION: us-east-1

- name: Print the Spanish customer changelog
  run: cat "$(jq -r '.customer.es' <<< "$FILES")"
  env:
    FILES: ${{ steps.release.outputs.changelog_files }}
```

Every audience/language pair is generated in parallel. The available presets are
`developer`, `customer`, `executive`, `marketing`, `security` and `ops`; see
[Presets](/llm-release-action/reference/changelog-config/#presets) for what each one sets.

## Override or build your own audience

Fields next to `preset` override it. Without a preset, every field starts from its default.

```yaml
changelog_config: |
  api-consumers:
    languages: [en]
    sections: [breaking, features, deprecations]
    tone: formal
    include_commits: true
    link_commits: true
    breaking_migration: true
    emojis: false

  internal-devs:
    preset: developer
    include_infrastructure: true
```

## Generate a title, summary and highlights

```yaml
changelog_config: |
  release-notes:
    preset: customer
    generate_title: true
    generate_summary: true
    generate_highlights: 3
    languages: [en, es, de, ja, zh]
```

The results are in the `metadata` output, e.g. `.["release-notes"].en.title`.

## Add instructions, a header and issue links

```yaml
changelog_config: |
  team:
    preset: customer
    instructions: |
      Readers demo the product. Start with a one-line summary of the release.
    header: "Linear release: https://linear.app/acme/releases/{version}"
    footer: "Changes since {previous_version}."
    link_issues: true
    issue_url_template: "https://linear.app/acme/issue/{id}"
```

`instructions` go to the model. `header` and `footer` are added as written, after
generation, with `{version}` and `{previous_version}` filled in; they count toward
`validation.max_length`. With `link_issues`, issue IDs mentioned in the commits
(`Fixes ACME-123`, a branch named `acme-123-...`) are linked on each entry.

## Filter what an audience sees

```yaml
changelog_config: |
  customer:
    preset: customer
    exclude_categories: [infrastructure, docs]
    exclude_labels: [internal]
    exclude_authors: [dependabot]
    exclude_patterns: ["^chore", "typo"]
```

The `customer`, `executive` and `marketing` presets also drop changes that people using
the release would not notice, such as test, CI or local development changes
(`user_facing_only: true`). Set `user_facing_only: false` to keep them, or `true` on any
other audience to drop them.

`exclude_patterns` are regexes matched against change titles. Patterns prone to
catastrophic backtracking (such as `(a+)+`) or longer than 200 characters are rejected.

See the [changelog config reference](/llm-release-action/reference/changelog-config/)
for every field, and [Keep internal details out of changelogs](/llm-release-action/how-to/filter-internal-content/)
for leak detection. To try a config before using it in a workflow, see
[Preview a changelog config locally](/llm-release-action/how-to/preview-changelog-config/).
