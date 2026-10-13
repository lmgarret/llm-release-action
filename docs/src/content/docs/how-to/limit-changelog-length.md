---
title: Limit changelog length
description: Enforce a hard character limit on a changelog, for example the 500-character limit of Google Play release notes.
sidebar:
  order: 6
---

Set `validation.max_length` below its default (100000) on the audience:

```yaml
changelog_config: |
  store:
    preset: customer
    output_format: plain
    validation:
      max_length: 500
```

The limit is enforced in three steps:

1. The prompt asks for at most 85% of `max_length`, dropping lowest-priority items first.
2. With `on_failure: retry` (the default), a changelog that fails validation is re-prompted with the errors, up to `max_retries` times (default 2).
3. If it is still too long, it is cut at the last complete line that fits.

`output_format: plain` avoids Markdown syntax that store consoles would show literally.
