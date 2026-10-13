---
title: Provide project context
description: Give the model README or architecture files so it can tell public APIs from internal code and detect breaking changes more accurately.
sidebar:
  order: 8
---

Point `context_files` at documentation describing what is public in your project:

```yaml
- uses: lmgarret/llm-release-action@v1
  with:
    model: bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0
    context_files: README.md,docs/ARCHITECTURE.md
```

[Why context helps](/llm-release-action/explanation/breaking-changes/#project-context) is explained separately.

## Write a context file

The most effective context is a short file listing what's public and what isn't, for
example `docs/CONTEXT.md`:

```markdown
# API Context

## Public APIs (breaking if changed)
- `/api/v2/*` - All v2 endpoints are public
- `AuthService.login()`, `AuthService.logout()` - Public auth methods
- `UserModel` - Public user data model

## Internal APIs (not breaking)
- `/internal/*` - Internal admin endpoints
- `_validate*` methods - Internal validation helpers
- `*Repository` classes - Internal data access

## Conventions
- All public methods have docstrings
- Internal methods start with underscore
```

## Select files with patterns

`context_files` takes comma-separated gitignore-style patterns, including negation:

```yaml
# Single file
context_files: README.md

# Several files
context_files: README.md,docs/ARCHITECTURE.md,docs/API.md

# Glob
context_files: "**/README.md"

# Glob with an exclusion
context_files: "**/README.md,!docs/internal/**"
```

Dependency, build, cache and IDE directories are always excluded; see
[Context file exclusions](/llm-release-action/reference/default-patterns/#context-file-exclusions).
These can't be turned off from the workflow.

## Raise the token budget

Context is capped at `context_max_tokens` (default 800). Larger content is summarized
with map/reduce to fit. Raise the cap for bigger documents:

```yaml
context_files: README.md,docs/**/*.md
context_max_tokens: 2000
```

## Act on staleness warnings

When changes touch areas your context doesn't mention, the action warns:

```
::warning::Changes detected in areas not covered by context: api, utils.
Consider updating your context files.
```

These also appear in the `warnings` output. Update the context file so future
analyses know whether those areas are public.
