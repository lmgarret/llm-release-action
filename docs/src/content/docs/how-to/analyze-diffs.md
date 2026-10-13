---
title: Analyze file diffs
description: Enable structured diff analysis so the model extracts semantic changes such as removed endpoints or dropped columns from file diffs.
sidebar:
  order: 9
---

By default, raw diffs of files matching `include_diffs` (OpenAPI specs, migrations,
protobuf) are added to the prompt and truncated to fit. With `analyze_diffs: true`, each
changed file's diff is first sent to the LLM, which extracts categorized changes and
flags breaking ones with migration notes. Nothing is lost to truncation.

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
    analyze_diffs: true
```

For example, this diff:

```diff
diff --git a/api/openapi.yaml b/api/openapi.yaml
@@ -45,6 +45,12 @@ paths:
+  /users/{id}/preferences:
+    get:
+      summary: Get user preferences
@@ -120,8 +126,6 @@ paths:
-  /users/{id}/settings:
-    get:
-      deprecated: true
```

becomes:

```json
{
  "file": "api/openapi.yaml",
  "changes": [
    { "type": "api_addition", "description": "Added GET /users/{id}/preferences endpoint", "breaking": false },
    {
      "type": "api_removal",
      "description": "Removed deprecated GET /users/{id}/settings endpoint",
      "breaking": true,
      "migration": "Use GET /users/{id}/preferences instead"
    }
  ]
}
```

## Exclude noisy files

Lock files, vendored and generated code are excluded by default
([full list](/llm-release-action/reference/default-patterns/#diff-exclusions)). Setting
`diff_exclude_patterns` replaces that list:

```yaml
analyze_diffs: true
diff_exclude_patterns: |
  **/package-lock.json,
  **/yarn.lock,
  **/vendor/**,
  **/*.generated.*,
  **/dist/**
```

## Control cost

Each analyzed file is one extra LLM call (run in parallel). Cap the number of files and
use a cheaper model for analysis:

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0
    model_analysis: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
    analyze_diffs: true
    diff_max_files: 30
```

When `diff_max_files` or `diff_max_total_lines` is exceeded, the action keeps the
highest-signal files ([prioritization order](/llm-release-action/reference/default-patterns/#diff-file-prioritization)),
warns with the number of skipped files, and continues.

If a release touches 100+ files, it is probably a refactoring better described by hand
than analyzed file by file.

## Combine with context files

```yaml
context_files: README.md,docs/API.md
analyze_diffs: true
```

Context files tell the model what is public; diff analysis tells it what changed.
Together they give the most accurate breaking change detection.
