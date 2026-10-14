---
title: Changelog config
description: Schema of the changelog_config input, the audience presets and their defaults.
sidebar:
  order: 3
---

`changelog_config` is YAML mapping audience names to their configuration. Each audience
name becomes a key in the `changelogs`, `changelog_files` and `metadata` outputs.

```yaml
changelog_config: |
  developer:
    preset: developer
  customer:
    preset: customer
    languages: [en, es, fr]
```

## Presets

A preset sets defaults; any field next to it overrides them.

| Preset | Description | Sections | Tone | User-facing only | Internal content check |
|--------|-------------|----------|------|------------------|------------------------|
| `developer` | Full technical changelog with commits, PRs, contributors | all 10 | professional | no | skipped |
| `customer` | User-facing changes, focused on benefits | breaking, features, improvements, fixes | friendly | yes | on |
| `executive` | High-level business summary | breaking, features | formal | yes | on |
| `marketing` | Promotional feature announcements | features, improvements | excited | yes | on |
| `security` | Security-focused with CVE details | security, breaking, fixes | formal | no | on |
| `ops` | Operations and DevOps | breaking, infrastructure, performance, security | professional | no | skipped |

Audiences without a preset keep every change (`user_facing_only: false`) and have the
internal content check on.

## Schema

```typescript
type ChangelogConfig = {
  [audienceName: string]: AudienceConfig
}

interface AudienceConfig {
  // Base preset; every field below then overrides it
  preset?: "developer" | "customer" | "executive" | "marketing" | "security" | "ops";

  // Languages to generate (ISO 639-1 codes)
  languages?: string[];               // default: ["en"]

  // Sections to include, in display order
  sections?: Section[];               // default: all sections

  // Content
  include_commits?: boolean;          // Show commit hashes, default: false
  include_contributors?: boolean;     // List authors, default: false
  include_infrastructure?: boolean;   // Include infra changes, default: true
  group_related?: boolean;            // Group related changes, default: true
  benefit_focused?: boolean;          // User benefits over technical details, default: false
  summary_only?: boolean;             // Brief summary instead of a full list, default: false

  // Filtering
  user_facing_only?: boolean;         // Drop changes only the project's developers notice, default: false
                                      // (true for customer, executive and marketing presets)
  exclude_categories?: Category[];    // Hide these categories
  exclude_patterns?: string[];        // Regexes matched against change titles
  exclude_labels?: string[];          // Exclude changes with these labels
  exclude_authors?: string[];         // Exclude changes by these authors
  max_items_per_section?: number;     // Limit items per section

  // Style
  emojis?: boolean;                   // default: false
  tone?: "formal" | "casual" | "professional" | "excited" | "friendly";

  // Breaking changes
  breaking_highlight?: boolean;       // Highlight breaking changes, default: true
  breaking_migration?: boolean;       // Include migration steps, default: true
  breaking_severity?: boolean;        // Show severity, default: true

  // Links (repository URL detected from the git remote)
  link_commits?: boolean;
  link_prs?: boolean;
  link_issues?: boolean;               // Issue tracker IDs found in commit messages
  issue_url_template?: string;        // Link for each ID, e.g. "https://linear.app/acme/issue/{id}";
                                      // without it, IDs are shown as plain text

  // Added by the workflow author
  instructions?: string;              // Extra instructions for the changelog prompt, max 4000 chars
  header?: string;                    // Text above the changelog, max 1000 chars
  footer?: string;                    // Text below the changelog, max 1000 chars

  // Metadata (written to the metadata output)
  generate_title?: boolean;           // Release title
  generate_summary?: boolean;         // 1-2 sentence summary
  generate_highlights?: number;       // Number of key highlights, e.g. 3

  // Output format
  output_format?: "markdown" | "html" | "json" | "plain";

  // Internal content detection
  skip_internal_check?: boolean;          // default: false (true for developer and ops presets)
  internal_domain_patterns?: string[];    // Extra regexes, added to the built-in ones

  // Output validation
  validation?: {
    enabled?: boolean;                // default: true
    min_length?: number;              // default: 50
    max_length?: number;              // default: 100000; lower values are enforced as a hard limit
    on_failure?: "retry" | "warn" | "error" | "fallback"; // default: "retry"
    max_retries?: number;             // Re-prompts when on_failure is "retry", default: 2
  };
}

type Section = "breaking" | "security" | "features" | "improvements"
             | "fixes" | "performance" | "deprecations"
             | "infrastructure" | "docs" | "other";

type Category = "breaking" | "security" | "feature" | "improvement"
              | "fix" | "performance" | "deprecation"
              | "infrastructure" | "docs" | "other";
```

## Constraints

- `user_facing_only`: Phase 1 tags each change as user-facing or not, based on the
  [project type](/llm-release-action/reference/project-types/). Tests, load tests, CI,
  local development setup and bugs that only occurred in development are not user-facing.
  Breaking changes always are.
- `link_issues`: the analysis picks up issue tracker IDs (`ABC-123`) from commit messages,
  including footers such as `Fixes ABC-123` and branch names in merge commits. IDs that
  don't appear verbatim in the commits are dropped.
- `instructions`: followed by the model unless they conflict with the length limit or ask
  it to invent hashes, numbers or links.
- `header`, `footer`: added verbatim after generation, with `{version}` and
  `{previous_version}` filled in. They count toward `validation.max_length`. Not supported
  with `output_format: json`.
- `exclude_patterns`: patterns with nested quantifiers such as `(a+)+` or longer than 200 characters are rejected; matching times out after 1 second.
- `internal_domain_patterns`: invalid regexes are silently skipped.
- `validation.max_length` below the default: see [Limit changelog length](/llm-release-action/how-to/limit-changelog-length/) for how it is enforced.
- If an audience's filters leave no changes, no LLM call is made and the changelog is "No changes in this release".
