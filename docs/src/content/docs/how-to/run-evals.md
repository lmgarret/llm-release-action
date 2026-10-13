---
title: Run the evals
description: Run the DeepEval suite that checks version bump accuracy, changelog quality and translation when contributing to the action.
sidebar:
  order: 15
---

The repository has a [DeepEval](https://github.com/confident-ai/deepeval) suite that
checks LLM output quality. It calls a real model, so it needs credentials (Bedrock by default).
Dependencies are managed with [uv](https://docs.astral.sh/uv/):

```bash
uv run --with deepeval pytest evals/ -v -m eval
```

DeepEval isn't in `uv.lock`: it holds back some of the action's own dependencies, so it is
added on top for the run only.

It covers:

- version bump accuracy (patch, minor, major),
- changelog quality and structure,
- breaking change detection,
- audience transformation (technical vs customer-friendly),
- translation quality.

Unit tests don't need credentials:

```bash
uv run pytest tests/
```

Lint and format with Ruff before pushing:

```bash
uv run ruff check --fix . && uv run ruff format .
```
