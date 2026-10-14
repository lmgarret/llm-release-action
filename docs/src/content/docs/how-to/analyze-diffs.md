---
title: Analyze file diffs
description: Choose which file diffs the model extracts semantic changes from, such as removed endpoints or dropped columns, and cap their size.
sidebar:
  order: 9
---

Diffs of files matching `diffs` (OpenAPI specs, migrations and protobuf by default) are
sent to `fast_model`, which extracts what was added, removed and modified. The result is
part of the analysis prompt, next to the commits, so a removed endpoint or dropped column
counts as evidence of a breaking change even when the commit message doesn't say so.

Point `diffs` at the files that define your public surface:

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0
    fast_model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
    diffs: "**/openapi*.yaml,**/migrations/**,src/public/**"
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

```
ADDED
- GET /users/{id}/preferences endpoint
REMOVED
- deprecated GET /users/{id}/settings endpoint
```

## Select files

`diffs` takes comma-separated gitignore-style patterns. Setting it replaces the
[defaults](/llm-release-action/reference/default-patterns/#diff-patterns). Exclude files
with `!`:

```yaml
diffs: "**/openapi*.yaml,src/**,!src/**/generated/**,!**/*.lock"
```

Set it to an empty string to turn diff analysis off:

```yaml
diffs: ""
```

## Control cost

Extraction runs on `fast_model`. `diff_max_lines` (default 5000) caps the
changed lines across all matched files:

```yaml
diff_max_lines: 2000
```

When the cap is exceeded, the action keeps the highest-signal files
([prioritization order](/llm-release-action/reference/default-patterns/#diff-file-prioritization)),
warns with the number of skipped files, and continues.

If a release touches 100+ files, it is probably a refactoring better described by hand
than analyzed file by file.

## Combine with context files

```yaml
context_files: README.md,docs/API.md
diffs: "**/openapi*.yaml"
```

Context files tell the model what is public; diffs tell it what changed.
Together they give the most accurate breaking change detection.
