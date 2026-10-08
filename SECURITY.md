# Security Policy

## Reporting Vulnerabilities

Please report security vulnerabilities by emailing nosov.joe@gmail.com.

Do not create public GitHub issues for security vulnerabilities.

## Security Considerations

### Data Sent to LLM Providers

This action sends the following data to your configured LLM provider:

- Commit messages (sanitized)
- Commit metadata (hashes, counts)
- File diffs for configured patterns (openapi, migrations, proto files by default)

**For repositories with sensitive commit messages, consider:**
- Using a self-hosted LLM
- Configuring `include_diffs` to exclude sensitive files
- Reviewing the prompt in debug mode before production use

### Prompt Injection Protection

Commit messages, context files and diffs can be written by anyone who can push
or open a pull request, so the action treats them as untrusted:

1. **Data boundaries**: every prompt embeds untrusted text inside a block whose
   closing tag carries a random nonce, and instructs the model never to follow
   instructions found there. Text is Unicode-normalized and the prompts' own
   structural tags (`<BUMP>`, `</PROJECT_CONTEXT>`, ...) are escaped, so content
   cannot close its block or forge a response section. Earlier model output
   (map/reduce, flatten, diff extraction) is treated the same way.
2. **Pattern scanning**: `content_override` is rejected on HIGH/CRITICAL
   findings. Commit messages, context files and diffs are scanned too, with
   findings reported in the `warnings` output rather than blocking.
3. **Input sanitization**: known injection phrases and XML-like tags are
   stripped from commit messages and change descriptions. These lists are
   defense in depth only.
4. **Output validation**: the bump must be exactly `major`, `minor`, or
   `patch`, and `next_version` is computed rather than taken from the model.
5. **Output sanitization**: changelogs and `reasoning` are sanitized per output
   format (HTML stripped from Markdown/plain text; allowlisted tags and safe
   link schemes only in HTML output). Multi-line outputs use a random
   `GITHUB_OUTPUT` delimiter.

No defense makes an LLM immune to manipulation: a crafted commit can still
influence the wording of a changelog or nudge the bump level. **Treat every
output as untrusted text.** Pass outputs to later steps through `env:`; never
interpolate `${{ steps.<id>.outputs.* }}` into `run:` or `github-script`
`script:` blocks, where it becomes shell or JavaScript code.

### API Key Security

- API keys are passed via environment variables
- GitHub Actions automatically masks secrets in logs
- Keys are never logged by this action

### Supply Chain Security

- Pin this action to a specific version: `@v1.0.0`
- Review the action source before use
- LiteLLM dependency is pinned to a specific version

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 1.x     | :white_check_mark: |
| < 1.0   | :x:                |
