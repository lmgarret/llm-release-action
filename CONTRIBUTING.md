# Contributing

## Reporting bugs and requesting features

Open a [GitHub issue](https://github.com/lmgarret/llm-release-action/issues).
For a bug, include the action version, the inputs you used and the warnings
or logs it printed.

Report security vulnerabilities privately as described in
[SECURITY.md](SECURITY.md), never in a public issue.

## Proposing changes

1. Fork the repository and create a branch from `master`.
2. Make your change, with tests (see below).
3. Open a pull request against `master`. CI must pass, and the maintainer
   reviews contributed pull requests before merging.

Pull request titles follow [Conventional Commits](https://www.conventionalcommits.org/)
(`feat:`, `fix:`, `docs:`, `chore:`...; `feat!:` for breaking changes), because
the action analyzes its own history to release itself. `CONTEXT.md` lists
what counts as a breaking change.

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/).
- Code passes `uv run ruff check .` and `uv run ruff format --check .`.
- Workflows and `action.yml` pass `uv run zizmor .`.
- New third-party GitHub Actions are pinned to a full commit SHA.
- User-facing changes update the documentation in [`docs/`](docs/).

## Tests

Run the test suite with:

```bash
uv run pytest
```

**Test policy:** new functionality and bug fixes come with automated tests in
[`tests/`](tests/) that cover them. A bug fix includes a test that fails
without the fix. Pull requests without tests are only merged when the change
cannot be tested meaningfully (documentation, CI configuration).

Prompt or model changes can also be checked against real models with the
evals described in [Run evals](https://lmgarret.github.io/llm-release-action/how-to/run-evals/).
