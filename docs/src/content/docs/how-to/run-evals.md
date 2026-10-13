---
title: Run the evals
description: Run the DeepEval suite that checks version bump accuracy, changelog quality and translation when contributing to the action.
sidebar:
  order: 15
---

The repository has a [DeepEval](https://github.com/confident-ai/deepeval) suite that
checks LLM output quality. It calls a real model, so it needs credentials (Bedrock by default).

```bash
pip install -r evals/requirements.txt
PYTHONPATH=src pytest evals/ -v -m eval
```

It covers:

- version bump accuracy (patch, minor, major),
- changelog quality and structure,
- breaking change detection,
- audience transformation (technical vs customer-friendly),
- translation quality.

Unit tests don't need credentials:

```bash
pip install -r src/requirements.txt -r tests/requirements.txt
PYTHONPATH=src pytest tests/
```
