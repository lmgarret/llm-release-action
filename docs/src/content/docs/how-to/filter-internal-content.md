---
title: Keep internal details out of changelogs
description: Configure the internal content check that warns when customer-facing changelogs mention internal repos, hosts, secrets or tickets.
sidebar:
  order: 7
---

The action checks customer-facing changelogs for internal details such as repository
names, internal hostnames, private IPs or tokens, and emits a warning when it finds
some. It is on by default for every audience except the `developer` and `ops` presets.
See [Internal content patterns](/llm-release-action/reference/default-patterns/#internal-content-patterns)
for what is detected.

## Add your organization's patterns

```yaml
changelog_config: |
  customer:
    preset: customer
    internal_domain_patterns:
      - "JIRA-\\d+"            # Internal ticket references
      - "\\bSLACK-\\w+"        # Slack channel IDs
      - "mycompany\\.internal" # Custom internal domain
```

Custom patterns are added to the built-in ones. Invalid regexes are silently skipped,
so test them before relying on them.

## Skip the check for an audience

```yaml
changelog_config: |
  internal-facing:
    preset: customer
    skip_internal_check: true
```

## Remove changes entirely

The check only warns. To keep changes out of an audience's changelog, filter them with
`user_facing_only`, `exclude_categories`, `exclude_labels`, `exclude_authors` or `exclude_patterns`; see
[Generate multi-audience changelogs](/llm-release-action/how-to/multi-audience-changelogs/#filter-what-an-audience-sees).
