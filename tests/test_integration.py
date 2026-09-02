"""Integration tests for the full analysis flow."""

import os
import sys
import tempfile
import subprocess
from unittest.mock import patch, MagicMock

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from analyze import (
    main,
    build_completion_kwargs,
    call_llm_with_retry,
    parse_extra_llm_params,
    sanitize_changelog,
)
from version import parse_version
from parser import parse_response
from prompt_builder import build_prompt, CommitInfo


class TestEndToEnd:
    """End-to-end integration tests."""

    def test_full_flow_with_mock_llm(self):
        """Test the complete flow from commits to version suggestion."""
        # Simulate commits
        commits = [
            CommitInfo(hash="abc1234", message="feat: add new login page"),
            CommitInfo(hash="def5678", message="fix: resolve login redirect bug"),
            CommitInfo(hash="ghi9012", message="chore: update dependencies"),
        ]

        # Build prompt
        prompt = build_prompt(commits, "v1.0.0")

        # Verify prompt contains expected content
        assert "v1.0.0 -> next" in prompt
        assert "3 total" in prompt
        assert "feat: add new login page" in prompt
        assert "fix: resolve login redirect bug" in prompt

        # Simulate LLM response
        mock_response = """
<BUMP>minor</BUMP>
<REASONING>New feature added (login page) with bug fix. No breaking changes detected.</REASONING>
<BREAKING_CHANGES>
</BREAKING_CHANGES>
<FEATURES>
- New login page
</FEATURES>
<FIXES>
- Login redirect bug fixed
</FIXES>
<CHANGELOG>
## What's Changed

### Features
- New login page

### Bug Fixes
- Login redirect bug fixed
</CHANGELOG>
"""

        # Parse response
        result = parse_response(mock_response)

        assert result.bump == "minor"
        assert "login page" in result.reasoning.lower()
        assert len(result.features) == 1
        assert len(result.fixes) == 1

        # Calculate next version
        current = parse_version("v1.0.0")
        next_version = current.bump(result.bump)

        assert str(next_version) == "v1.1.0"

    def test_breaking_change_flow(self):
        """Test flow with breaking change detected."""
        commits = [
            CommitInfo(
                hash="abc1234",
                message="feat!: remove deprecated API endpoint",
                has_breaking_marker=True,
            ),
            CommitInfo(hash="def5678", message="fix: update error messages"),
        ]

        prompt = build_prompt(commits, "v2.0.0")

        assert "[BREAKING]" in prompt
        assert "Explicit BREAKING markers**: 1" in prompt

        # Simulate LLM response for breaking change
        mock_response = """
<BUMP>major</BUMP>
<REASONING>Breaking change detected: API endpoint removed.</REASONING>
<BREAKING_CHANGES>
- Deprecated API endpoint removed
</BREAKING_CHANGES>
<FEATURES>
</FEATURES>
<FIXES>
- Error messages updated
</FIXES>
<CHANGELOG>
## What's Changed

### Breaking Changes
- Deprecated API endpoint removed

### Bug Fixes
- Error messages updated
</CHANGELOG>
"""

        result = parse_response(mock_response)

        assert result.bump == "major"
        assert len(result.breaking_changes) == 1

        current = parse_version("v2.0.0")
        next_version = current.bump(result.bump)

        assert str(next_version) == "v3.0.0"

    def test_patch_only_flow(self):
        """Test flow with only bug fixes."""
        commits = [
            CommitInfo(hash="abc1234", message="fix: resolve memory leak"),
            CommitInfo(hash="def5678", message="fix: correct typo in error message"),
            CommitInfo(hash="ghi9012", message="docs: update readme"),
        ]

        prompt = build_prompt(commits, "v1.5.2")

        mock_response = """
<BUMP>patch</BUMP>
<REASONING>Only bug fixes and documentation updates. No new features.</REASONING>
<BREAKING_CHANGES>
</BREAKING_CHANGES>
<FEATURES>
</FEATURES>
<FIXES>
- Memory leak resolved
- Typo in error message corrected
</FIXES>
<CHANGELOG>
## What's Changed

### Bug Fixes
- Memory leak resolved
- Typo in error message corrected
</CHANGELOG>
"""

        result = parse_response(mock_response)

        assert result.bump == "patch"
        assert len(result.fixes) == 2

        current = parse_version("v1.5.2")
        next_version = current.bump(result.bump)

        assert str(next_version) == "v1.5.3"


class TestLLMRetry:
    """Tests for LLM retry logic."""

    def test_retry_on_rate_limit(self):
        """Test retry on 429 rate limit."""
        mock_completion = MagicMock()

        # First call fails with rate limit, second succeeds
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "<BUMP>patch</BUMP><REASONING>test</REASONING>"

        mock_completion.side_effect = [
            Exception("429 rate limit exceeded"),
            mock_response,
        ]

        with patch("analyze.litellm.completion", mock_completion):
            with patch("analyze.time.sleep"):  # Skip actual sleep
                result, usage = call_llm_with_retry(
                    model="test/model",
                    prompt="test prompt",
                    temperature=0.2,
                    max_tokens=100,
                    timeout=30,
                )

        assert "<BUMP>patch</BUMP>" in result
        assert mock_completion.call_count == 2
        assert usage.model == "test/model"

    def test_no_retry_on_auth_error(self):
        """Test immediate failure on auth error."""
        mock_completion = MagicMock()
        mock_completion.side_effect = Exception("401 authentication failed")

        with patch("analyze.litellm.completion", mock_completion):
            with pytest.raises(RuntimeError) as exc_info:
                call_llm_with_retry(
                    model="test/model",
                    prompt="test prompt",
                    temperature=0.2,
                    max_tokens=100,
                    timeout=30,
                )

        assert "Authentication failed" in str(exc_info.value)
        assert mock_completion.call_count == 1  # No retries

    def test_max_retries_exceeded(self):
        """Test failure after max retries."""
        mock_completion = MagicMock()
        mock_completion.side_effect = Exception("500 server error")

        with patch("analyze.litellm.completion", mock_completion):
            with patch("analyze.time.sleep"):
                with pytest.raises(RuntimeError) as exc_info:
                    call_llm_with_retry(
                        model="test/model",
                        prompt="test prompt",
                        temperature=0.2,
                        max_tokens=100,
                        timeout=30,
                        max_retries=3,
                    )

        assert "failed after 3 attempts" in str(exc_info.value)
        assert mock_completion.call_count == 3


class TestChangelogSanitization:
    """Tests for changelog sanitization."""

    def test_strips_html(self):
        """Test HTML tags are stripped."""
        changelog = "## Changes\n<script>alert('xss')</script>\n- Fixed bug"
        result = sanitize_changelog(changelog)

        assert "<script>" not in result
        assert "## Changes" in result
        assert "Fixed bug" in result

    def test_removes_javascript_urls(self):
        """Test javascript: URLs are removed."""
        changelog = "## Changes\n[Click here](javascript:alert('xss'))\n- Fixed bug"
        result = sanitize_changelog(changelog)

        assert "javascript:" not in result

    def test_truncates_large_changelog(self):
        """Test large changelog is truncated."""
        changelog = "x" * 100000
        result = sanitize_changelog(changelog, max_size=1000)

        assert len(result.encode("utf-8")) <= 1000
        assert "(truncated)" in result


class TestPreReleaseVersioning:
    """Tests for pre-release version handling."""

    def test_prerelease_patch_bump(self):
        """Test patch bump on pre-release version."""
        current = parse_version("v1.0.0-alpha.1")
        next_version = current.bump("patch")

        assert str(next_version) == "v1.0.0-alpha.2"

    def test_prerelease_minor_bump(self):
        """Test minor bump on pre-release version resets to stable."""
        current = parse_version("v1.0.0-alpha.1")
        next_version = current.bump("minor")

        assert str(next_version) == "v1.1.0"

    def test_prerelease_major_bump(self):
        """Test major bump on pre-release version resets to stable."""
        current = parse_version("v1.0.0-beta.5")
        next_version = current.bump("major")

        assert str(next_version) == "v2.0.0"


class TestParseCommitsJson:
    """Tests for external commits JSON parsing (multi-repo mode)."""

    def test_parse_basic_commits(self):
        """Test parsing basic commit list."""
        from analyze import parse_commits_json

        json_str = '''[
            {"hash": "abc1234", "message": "feat: add new feature"},
            {"hash": "def5678", "message": "fix: resolve bug"}
        ]'''

        commits = parse_commits_json(json_str)

        assert len(commits) == 2
        assert commits[0].hash == "abc1234"
        assert "add new feature" in commits[0].message
        assert commits[1].hash == "def5678"

    def test_parse_with_repo_prefix(self):
        """Test parsing commits with repo field."""
        from analyze import parse_commits_json

        json_str = '''[
            {"hash": "abc1234", "message": "feat: add login", "repo": "frontend"},
            {"hash": "def5678", "message": "fix: api error", "repo": "backend"}
        ]'''

        commits = parse_commits_json(json_str)

        assert len(commits) == 2
        assert commits[0].hash == "[frontend] abc1234"
        assert commits[1].hash == "[backend] def5678"

    def test_parse_detects_breaking_changes(self):
        """Test breaking change detection in JSON commits."""
        from analyze import parse_commits_json

        json_str = '''[
            {"hash": "abc1234", "message": "feat!: breaking change here"},
            {"hash": "def5678", "message": "fix: normal fix"}
        ]'''

        commits = parse_commits_json(json_str)

        assert commits[0].has_breaking_marker is True
        assert commits[1].has_breaking_marker is False

    def test_parse_invalid_json(self):
        """Test error on invalid JSON."""
        from analyze import parse_commits_json

        with pytest.raises(ValueError) as exc_info:
            parse_commits_json("not valid json")

        assert "Invalid commits_json" in str(exc_info.value)

    def test_parse_not_array(self):
        """Test error when JSON is not array."""
        from analyze import parse_commits_json

        with pytest.raises(ValueError) as exc_info:
            parse_commits_json('{"hash": "abc"}')

        assert "must be a JSON array" in str(exc_info.value)

    def test_parse_missing_required_fields(self):
        """Test error when commit missing required fields."""
        from analyze import parse_commits_json

        json_str = '[{"hash": "abc1234"}]'  # Missing message

        with pytest.raises(ValueError) as exc_info:
            parse_commits_json(json_str)

        assert "missing required fields" in str(exc_info.value)

    def test_parse_sanitizes_messages(self):
        """Test that commit messages are sanitized."""
        from analyze import parse_commits_json

        json_str = '''[
            {"hash": "abc1234", "message": "feat: add <script>bad</script> feature"}
        ]'''

        commits = parse_commits_json(json_str)

        assert "<script>" not in commits[0].message
        assert "add" in commits[0].message
        assert "feature" in commits[0].message


# Models used across the kwargs tests
NEW_MODEL = "anthropic/claude-sonnet-5"          # rejects sampling, thinks by default
OLD_MODEL = "anthropic/claude-sonnet-4-5-20250929"  # accepts sampling, no thinking
NO_THINK_MODEL = "anthropic/claude-opus-4-7"     # rejects sampling, no thinking


def _mock_response(content="ok"):
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = content
    response.usage.prompt_tokens = 1
    response.usage.completion_tokens = 1
    response.usage.total_tokens = 2
    return response


def _forwarded_kwargs(**call_kwargs):
    """Call the wrapper and return the kwargs it actually forwarded to litellm."""
    mock_completion = MagicMock(return_value=_mock_response())
    call_kwargs.setdefault("prompt", "test prompt")
    call_kwargs.setdefault("timeout", 30)
    with patch("analyze.litellm.completion", mock_completion):
        call_llm_with_retry(**call_kwargs)
    return mock_completion.call_args.kwargs


class TestCompletionKwargs:
    """The parameters actually forwarded to litellm.completion.

    These assertions are the gap that let the `temperature is deprecated`
    failure ship: the existing retry tests never inspected call_args.
    """

    def test_temperature_dropped_for_new_model(self):
        kwargs = _forwarded_kwargs(model=NEW_MODEL, temperature=0.2, max_tokens=4000)
        assert "temperature" not in kwargs
        assert kwargs["model"] == NEW_MODEL

    def test_temperature_kept_for_older_model(self):
        kwargs = _forwarded_kwargs(model=OLD_MODEL, temperature=0.2, max_tokens=4000)
        assert kwargs["temperature"] == 0.2
        assert kwargs["max_tokens"] == 4000

    def test_temperature_kept_for_non_anthropic(self):
        kwargs = _forwarded_kwargs(
            model="openai/gpt-4o-mini", temperature=0.7, max_tokens=4000
        )
        assert kwargs["temperature"] == 0.7

    def test_temperature_none_is_omitted_everywhere(self):
        for model in (NEW_MODEL, OLD_MODEL, "openai/gpt-4o-mini"):
            kwargs = _forwarded_kwargs(model=model, temperature=None, max_tokens=4000)
            assert "temperature" not in kwargs, model

    def test_max_tokens_floor_applied_for_thinking_model(self):
        # The regression from the report: the YES/NO injection check asks for 10
        # tokens, which thinking consumes entirely, yielding empty content.
        kwargs = _forwarded_kwargs(model=NEW_MODEL, temperature=0.0, max_tokens=10)
        assert kwargs["max_tokens"] >= 4096

    def test_max_tokens_untouched_for_older_model(self):
        kwargs = _forwarded_kwargs(model=OLD_MODEL, temperature=0.0, max_tokens=10)
        assert kwargs["max_tokens"] == 10

    def test_max_tokens_floor_never_lowers_a_larger_request(self):
        kwargs = _forwarded_kwargs(model=NEW_MODEL, temperature=None, max_tokens=8000)
        assert kwargs["max_tokens"] == 8000

    def test_no_floor_when_thinking_disabled(self):
        kwargs = _forwarded_kwargs(
            model=NEW_MODEL, temperature=None, max_tokens=10, thinking="off"
        )
        assert kwargs["max_tokens"] == 10

    def test_thinking_omitted_by_default(self):
        kwargs = _forwarded_kwargs(model=NEW_MODEL, temperature=None, max_tokens=4000)
        assert "thinking" not in kwargs

    def test_thinking_adaptive_forwarded(self):
        kwargs = _forwarded_kwargs(
            model=NO_THINK_MODEL, temperature=None, max_tokens=100, thinking="adaptive"
        )
        assert kwargs["thinking"] == {"type": "adaptive"}
        # opus-4.7 does not think unless asked, so asking must also raise the floor
        assert kwargs["max_tokens"] >= 4096

    def test_thinking_off_forwarded(self):
        kwargs = _forwarded_kwargs(
            model=NEW_MODEL, temperature=None, max_tokens=4000, thinking="off"
        )
        assert kwargs["thinking"] == {"type": "disabled"}

    def test_thinking_not_sent_to_non_anthropic(self):
        kwargs = _forwarded_kwargs(
            model="openai/gpt-4o-mini",
            temperature=None,
            max_tokens=4000,
            thinking="adaptive",
        )
        assert "thinking" not in kwargs

    def test_extra_params_merged(self):
        kwargs = _forwarded_kwargs(
            model=NEW_MODEL,
            temperature=None,
            max_tokens=4000,
            extra_params={"reasoning_effort": "low"},
        )
        assert kwargs["reasoning_effort"] == "low"

    def test_extra_params_override_capability_decision(self):
        # The escape hatch: force a parameter back on when the table is wrong.
        kwargs = _forwarded_kwargs(
            model=NEW_MODEL,
            temperature=0.2,
            max_tokens=4000,
            extra_params={"temperature": 0.9},
        )
        assert kwargs["temperature"] == 0.9

    def test_baseline_kwargs_always_present(self):
        kwargs = _forwarded_kwargs(model=OLD_MODEL, temperature=0.2, max_tokens=4000)
        assert kwargs["messages"] == [{"role": "user", "content": "test prompt"}]
        assert kwargs["timeout"] == 30


class TestWarnOnce:
    """A fan-out phase must not repeat the same warning per thread."""

    def test_temperature_warning_emitted_once(self, capsys):
        import analyze

        analyze._warned.clear()
        for _ in range(3):
            build_completion_kwargs(
                model=NEW_MODEL,
                prompt="p",
                temperature=0.2,
                max_tokens=4000,
                timeout=30,
            )
        output = capsys.readouterr().out
        assert output.count("does not accept `temperature`") == 1

    def test_unsupported_thinking_opt_out_warns(self, capsys):
        import analyze

        analyze._warned.clear()
        kwargs = build_completion_kwargs(
            model="claude-fable-5-1",
            prompt="p",
            temperature=None,
            max_tokens=4000,
            timeout=30,
            thinking="off",
        )
        assert "thinking" not in kwargs
        assert "does not support `thinking: off`" in capsys.readouterr().out


class TestParseExtraLLMParams:
    """extra_llm_params must reject anything that is not a JSON object."""

    def test_empty_is_none(self):
        assert parse_extra_llm_params("") is None
        assert parse_extra_llm_params("   ") is None

    def test_object_parsed(self):
        assert parse_extra_llm_params('{"reasoning_effort": "low"}') == {
            "reasoning_effort": "low"
        }

    def test_invalid_json_rejected(self):
        with pytest.raises(ValueError, match="Invalid JSON"):
            parse_extra_llm_params("{not json}")

    def test_non_object_rejected(self):
        with pytest.raises(ValueError, match="must be a JSON object"):
            parse_extra_llm_params('["a", "b"]')
