# Security Policy

## Reporting Vulnerabilities

Please report security vulnerabilities through
[GitHub private vulnerability reporting](https://github.com/lmgarret/llm-release-action/security/advisories/new).

Do not create public GitHub issues for security vulnerabilities.

## Security Considerations

### Data Sent to LLM Providers

This action sends the following data to your configured LLM provider:

- Commit messages (sanitized)
- Commit metadata (hashes, counts)
- File diffs matching `diffs` (openapi, migrations, proto files by default)
- Context files matching `context_files` (`README.md` by default)

**For repositories with sensitive commit messages, consider:**
- Using a self-hosted LLM
- Narrowing `diffs` and `context_files`, or excluding sensitive files with `!` patterns
- Reviewing the prompts with GitHub debug logging (`ACTIONS_STEP_DEBUG`) before production use

### Prompt Injection Protection

Commit messages, context files and diffs can be written by anyone who can push
or open a pull request. The action does not try to detect malicious content in
them; instead it keeps that text as data from end to end:

1. **Nothing generated is executed**: the action has no `eval`, calls git with
   argument lists, and gives the model no tools and no secrets.
2. **Data boundaries**: every prompt embeds untrusted text inside a block whose
   closing tag carries a random nonce, and instructs the model never to follow
   instructions found there. Text is Unicode-normalized and the prompts' own
   structural tags (`<BUMP>`, `</PROJECT_CONTEXT>`, ...) are escaped, so content
   cannot close its block or forge a response section. Earlier model output
   (map/reduce, flatten, diff extraction) is treated the same way.
3. **Constrained results**: the bump must be exactly `major`, `minor`, or
   `patch`, and `next_version` is computed rather than taken from the model.
   A manipulated response can at worst produce a wrong bump level or
   misleading changelog text.
4. **Inert outputs**: multi-line outputs use a random `GITHUB_OUTPUT`
   delimiter, and `changelog_files` lets later steps use a changelog without
   handling its text in shell. `output_format: html` changelogs are reduced to
   an allowlist of structural tags because that format is meant to be
   inserted as markup; Markdown and plain text are output unchanged.

`content_override` is additionally pattern-scanned and rejected on high-risk
findings.

**Treat every output as untrusted text.** Pass outputs to later steps through
`env:` or use `changelog_files`; never interpolate `${{ steps.<id>.outputs.* }}`
into `run:` or `github-script` `script:` blocks, where it becomes shell or
JavaScript code. Escape Markdown changelogs for whatever renders them.

### API Key Security

- API keys are passed via environment variables
- GitHub Actions automatically masks secrets in logs
- Keys are never logged by this action

### Supply Chain Security

- Pin this action to a full commit SHA (`@<sha> # v1.2.0`) and let Dependabot
  bump it; `@v2` moves with every release
- Review the action source before use
- All Python dependencies, transitive ones included, are pinned with hashes and
  installed with `--require-hashes`
- Release tags (`vX.Y.Z`) and their releases are immutable

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| < 2.0   | :x:                |
