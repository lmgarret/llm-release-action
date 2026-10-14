---
title: How it works
description: The phases of a run, from collecting commits to writing audience-specific changelogs, and how large inputs are handled.
sidebar:
  order: 1
---

A run collects the changes since the last release, turns them into structured data, then
rewrites that data once per audience and language.

```
commits, diffs, context ──► Phase 0: flatten ──► Phase 1: analyze ──► Phase 2: write
                                (net state)       (changes + bump)     (per audience × language)
```

## Inputs gathered

- **Commits** between the base ref (`base_ref`, else the nearest tag matching `tag_pattern`, else the start of history) and `head_ref`.
- **Diff changes**: diffs of files matching `diffs` (OpenAPI specs, migrations, protobuf by default), turned into added, removed and modified items by `fast_model`.
- **Project context** from `context_files` (the root `README.md` by default), summarized by `fast_model` to fit `context_max_tokens`.
- **Project type**, detected from the README and file layout when `project_type: auto`.

With `content_override`, the provided Markdown replaces commits and diffs.

Consolidation, analysis and changelog writing run on `model`; the gathering calls above
run on `fast_model`.

## Phase 0: flatten

Changes are read chronologically to find the **net state** of the release: work that was
reverted disappears, and follow-up fixes merge into the change they fix. See
[Changelog consolidation](/llm-release-action/explanation/consolidation/).

## Phase 1: semantic analysis

The flattened changes become structured records: category, importance, user benefit,
technical detail, and breaking change information with severity and migration steps.
From them the model chooses the bump, following the
[versioning rules](/llm-release-action/reference/versioning-rules/) for the project type,
and explains its choice in `reasoning`.

The action validates the answer (`bump` must be exactly `major`, `minor` or `patch`) and
computes `next_version` itself, from `current_version` or the semver base tag. Without
either, `next_version` is empty.

## Phase 2: changelog generation

For every audience and language in `changelog_config`, the structured changes are
filtered (sections, excluded categories, labels, authors, patterns), then rewritten with
the audience's tone, format and language. All pairs run in parallel. Each result is
validated (length, internal content) and retried or truncated per the audience's
`validation` settings.

Phase 2 never sees the commits, only Phase 1's structured changes, so every audience
describes the same facts.

## Large inputs: map/reduce

When the input exceeds about 8000 tokens, Phase 1 switches to map/reduce:

1. **Split** the content into chunks.
2. **Map**: extract changes from each chunk in parallel.
3. **Reduce**: deduplicate the results, then flatten them as in Phase 0.

The same technique summarizes context files larger than `context_max_tokens` and large
`content_override` inputs. Summarization is reported in `warnings`.
