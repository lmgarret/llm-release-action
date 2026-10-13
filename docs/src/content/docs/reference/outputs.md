---
title: Outputs
description: Every output of lmgarret/llm-release-action with its type, schema and an example value.
sidebar:
  order: 2
---

Structured outputs are JSON strings. Parse them with `jq` or `fromJSON()`. Outputs
containing LLM text are untrusted: [use them safely](/llm-release-action/how-to/use-outputs-safely/).

| Output | Type | Description |
|--------|------|-------------|
| `bump` | `string` | `major`, `minor` or `patch`. |
| `current_version` | `string` | Version compared from (detected or provided). |
| `next_version` | `string` | Next semantic version, e.g. `v1.2.0`. Computed by the action, never taken from the model. |
| `changelogs` | `{[audience]: {[lang]: string}}` | Changelog text per audience and language. |
| `changelog_files` | `{[audience]: {[lang]: string}}` | Path of a file holding each changelog. |
| `metadata` | `{[audience]: {[lang]: Metadata}}` | Release title, summary and highlights. |
| `changes` | `Change[]` | Structured changes from the analysis. |
| `stats` | `Stats` | Change counts per category and contributor count. |
| `breaking_changes` | `BreakingChange[]` | Breaking changes with severity and migration steps. |
| `reasoning` | `string` | The model's explanation for the bump. |
| `project_type` | `string` | Project type used: `library`, `api`, `service`, `app` or `generic`. |
| `usage` | `{[model]: UsageStats}` | Calls, tokens and latency per model. |
| `warnings` | `string[]` | Warnings about context staleness, summarization, skipped files, etc. |

## `changelogs`

```typescript
type Changelogs = {
  [audience: string]: {
    [language: string]: string  // Content in the audience's output_format
  }
}
```

Without `changelog_config`: `{"default": {"en": "..."}}`.

```json
{
  "customer": {
    "en": "## What's New\n\n### ✨ Features\n- **Dark Mode** - Easier on the eyes...",
    "es": "## Novedades\n\n### ✨ Características\n- **Modo Oscuro** - Más fácil para los ojos..."
  },
  "developer": {
    "en": "## Changelog\n\n### Breaking Changes\n- Removed deprecated `/api/v1` endpoints..."
  }
}
```

Each changelog is at most 64KB.

## `changelog_files`

Same shape as `changelogs`, with each value replaced by a file path. Files are written to
a fresh directory under `$RUNNER_TEMP` (outside the checkout, emptied by the runner after
the job) and named `<audience>.<language>.<ext>`, where the extension follows the
audience's `output_format`: `.md`, `.html` or `.txt`.

```json
{
  "customer": {
    "en": "/home/runner/work/_temp/llm-release-action-k2j4/customer.en.md",
    "es": "/home/runner/work/_temp/llm-release-action-k2j4/customer.es.md"
  }
}
```

Only later steps of the same job can read them. Use `actions/upload-artifact` to pass
one to another job.

## `metadata`

```typescript
type MetadataOutput = {
  [audience: string]: {
    [language: string]: Metadata
  }
}

interface Metadata {
  title: string | null;    // if generate_title: true
  summary: string | null;  // 1-2 sentences, if generate_summary: true
  highlights: string[];    // if generate_highlights > 0
}
```

```json
{
  "customer": {
    "en": {
      "title": "February Release: Dark Mode & Performance",
      "summary": "This release brings the long-awaited dark mode and 2x faster load times.",
      "highlights": ["Dark mode support", "50% faster page loads", "New dashboard widgets"]
    }
  }
}
```

## `changes`

```typescript
interface Change {
  id: string;
  category: Category;
  title: string;                     // Short description
  description: string;               // Detailed description
  commits: string[];                 // Commit hashes
  authors: string[];
  importance: "high" | "medium" | "low";
  user_benefit: string | null;       // What users gain
  technical_detail: string | null;   // Implementation details
  breaking: BreakingInfo | null;
  labels: string[];
  source: string | null;             // Source repo (content_override)
  pr_number: number | null;
  issue_numbers: number[];
}

type Category = "breaking" | "security" | "feature" | "improvement"
              | "fix" | "performance" | "deprecation"
              | "infrastructure" | "docs" | "other";

interface BreakingInfo {
  severity: "high" | "medium" | "low";
  affected: string;                  // What is affected
  migration: string[];               // Migration steps
}
```

```json
[
  {
    "id": "change-1",
    "category": "feature",
    "title": "Add dark mode support",
    "description": "Users can now toggle between light and dark themes",
    "commits": ["abc1234", "def5678"],
    "authors": ["alice", "bob"],
    "importance": "high",
    "user_benefit": "Reduced eye strain during nighttime use",
    "technical_detail": "Implemented via CSS variables with system preference detection",
    "breaking": null,
    "labels": ["ui", "accessibility"],
    "source": null,
    "pr_number": 123,
    "issue_numbers": [100, 101]
  },
  {
    "id": "change-2",
    "category": "breaking",
    "title": "Remove deprecated API v1 endpoints",
    "description": "All /api/v1/* endpoints have been removed",
    "commits": ["ghi9012"],
    "authors": ["charlie"],
    "importance": "high",
    "user_benefit": null,
    "technical_detail": null,
    "breaking": {
      "severity": "high",
      "affected": "API consumers using v1 endpoints",
      "migration": ["Update base URL from /api/v1 to /api/v2", "Update auth header format"]
    },
    "labels": ["api"],
    "source": null,
    "pr_number": 456,
    "issue_numbers": []
  }
]
```

## `stats`

```typescript
interface Stats {
  features: number;
  fixes: number;
  improvements: number;
  breaking: number;
  security: number;
  performance: number;
  deprecations: number;
  infrastructure: number;
  docs: number;
  other: number;
  contributors: number;  // Unique authors
}
```

```json
{
  "features": 5, "fixes": 12, "improvements": 3, "breaking": 1, "security": 0,
  "performance": 2, "deprecations": 1, "infrastructure": 4, "docs": 2, "other": 0,
  "contributors": 8
}
```

## `breaking_changes`

```typescript
interface BreakingChange {
  title: string;
  severity: "high" | "medium" | "low";
  affected: string;
  migration: string[];
}
```

```json
[
  {
    "title": "Remove deprecated API v1 endpoints",
    "severity": "high",
    "affected": "API consumers using v1 endpoints",
    "migration": ["Update base URL from /api/v1 to /api/v2", "Update auth header format"]
  }
]
```

## `usage`

```typescript
type Usage = {
  [model: string]: {
    calls: number;
    input_tokens: number;
    output_tokens: number;
    latency_ms: number;    // Total across calls
  }
}
```

```json
{
  "bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0": {
    "calls": 4,
    "input_tokens": 1882,
    "output_tokens": 1126,
    "latency_ms": 8843
  }
}
```
