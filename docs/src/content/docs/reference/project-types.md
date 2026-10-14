---
title: Project types
description: The project types accepted by project_type and what each one treats as a breaking change.
sidebar:
  order: 4
---

| Type | Consumers | Breaking when |
|------|-----------|---------------|
| `library` | Developers calling it (packages, SDKs, CLI tools, GitHub Actions) | Public functions, flags, inputs or outputs removed or changed; runtime support dropped |
| `api` | External clients over the network | Endpoints or fields removed or changed; auth or error formats changed |
| `service` | Operators deploying it themselves | Config or env vars renamed or newly required; manual upgrade steps |
| `app` | End users | Minimum OS raised; features removed; user data lost; manual user action needed |
| `generic` | Unknown | Type-agnostic rules |

For every type, a change is breaking only if an existing consumer has to act.
Irreversibility alone (no rollback or downgrade) does not make a change breaking.

## `auto` detection

With `project_type: auto` (default), one LLM call with `fast_model` classifies the
project from:

- the root README,
- a two-level listing of tracked files (e.g. `app/build.gradle.kts`, `fastlane/metadata/`, `package.json`, `api/openapi.yaml`, `Dockerfile`).

Low-confidence results fall back to `generic`. With `content_override`, detection is
skipped and the type is `generic` unless set explicitly.

## Effect on the default changelog

None. Without `changelog_config`, the `default` audience always uses the `developer`
preset. For a user-facing changelog, for example for an app, set:

```yaml
changelog_config: "default: {preset: customer}"
```
