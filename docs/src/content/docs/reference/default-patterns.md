---
title: Default patterns
description: Built-in exclusions for context files and diff analysis, diff file prioritization, and internal content detection patterns.
sidebar:
  order: 6
---

## Context file exclusions

These directories are always excluded from `context_files` matching. They can't be
turned off from the workflow.

| Category | Directories |
|----------|-------------|
| Dependencies | `node_modules`, `vendor`, `.pnpm`, `Pods`, `.dart_tool`, `.gradle`, `elm-stuff`, `_build`, `deps`, `.bundle`, `.cargo` |
| Python | `__pycache__`, `.pytest_cache`, `.venv`, `venv`, `.tox`, `.mypy_cache`, `.ruff_cache`, `htmlcov`, `*.egg-info` |
| Build | `dist`, `build`, `target`, `out` |
| Caches | `.cache`, `.parcel-cache`, `.turbo` |
| Frameworks | `.next`, `.nuxt`, `.output`, `.svelte-kit`, `storybook-static` |
| Coverage | `coverage`, `.nyc_output` |
| IDE/Editor | `.idea`, `.vscode`, `.vs` |
| Infra/Deploy | `.terraform`, `.serverless`, `.vercel`, `.netlify` |
| Generated docs | `site`, `_site`, `docs/_build` |
| Other | `.git`, `logs`, `.logs`, `tmp`, `temp`, `.tmp` |

## Diff exclusions

Default of `diff_exclude_patterns`. Setting the input replaces the whole list.

```
**/*.lock
**/package-lock.json
**/yarn.lock
**/Cargo.lock
**/poetry.lock
**/vendor/**
**/node_modules/**
**/*.generated.*
**/generated/**
**/*.min.js
**/*.min.css
```

## Diff file prioritization

When `diff_max_files` or `diff_max_total_lines` is exceeded, files are kept in this order:

1. API specs: `openapi*.yaml`, `*.proto`, `*.graphql`
2. Database migrations: `**/migrations/**`
3. Configuration: `*.config.*`, `Dockerfile`, CI files
4. Other files, largest diff first

Skipped files are reported in `warnings`.

## Internal content patterns

The internal content check flags:

| Kind | Example |
|------|---------|
| Repository references | `org/repo` |
| AWS ARNs | `arn:aws:s3:::bucket-name` |
| Internal domains | `*.internal.*`, `*.local.*`, `*.corp.*`, `*.private.*` |
| Slack webhooks | `hooks.slack.com/...` |
| API keys and tokens | `api_key=...`, `token=...`, `secret=...` |
| Private IP addresses | `10.x.x.x`, `192.168.x.x`, `172.16-31.x.x` |
| Infrastructure terms | CI/CD, GitHub Actions, database schema |

Add your own with `internal_domain_patterns`; see [Keep internal details out of changelogs](/llm-release-action/how-to/filter-internal-content/).
