---
title: Preview a changelog config locally
description: Try a changelog_config against a real repository before wiring it into a workflow, and iterate on it without re-analyzing commits.
sidebar:
  order: 16
---

`scripts/preview.py` runs the same pipeline as the action against a local checkout
and prints each audience/language changelog. It needs [uv](https://docs.astral.sh/uv/)
and your provider's credentials in the environment (for example `ANTHROPIC_API_KEY`).

Put the YAML you would pass as `changelog_config` in a file, then replay a past release:

```bash
./scripts/preview.py --repo ../my-app --from v1.4.0 --to v1.5.0 \
  --model anthropic/claude-sonnet-5-5 --config changelog.yml \
  --save-changes changes.json
```

`--from` must be an existing tag or commit. Unlike the action, the script does not
fall back to the full history when the base ref is missing.

## Iterate on the config

Edit `changelog.yml`, then regenerate only the changelogs from the saved analysis:

```bash
./scripts/preview.py --repo ../my-app --model anthropic/claude-sonnet-5-5 \
  --config changelog.yml --changes changes.json
```

Reusing `--changes` skips commit analysis, so each iteration is cheaper and
differences come from the config alone.

Each audience is generated independently, so you can compare variants side by
side by defining them as separate audiences in one config:

```yaml
team-friendly:
  preset: customer
  tone: friendly
  benefit_focused: true
team-short:
  preset: executive
  summary_only: true
```

## Other options

- `--input NAME=VALUE` passes any other [action input](/llm-release-action/reference/inputs/), for example `--input max_tokens=8000`.
- `--context-files` and `--project-type` match the inputs of the same name.
- `--out-dir DIR` also writes `<audience>.<language>.md` files.
- `--raw` prints the Markdown source instead of rendering it.
- `--verbose` shows the action's own logs.

Run `./scripts/preview.py --help` for the full list.
