"""Tests for diff analysis, llm_params and content_override input validation.

Tests cover:
1. validate_diff_max_lines - non-negative integer validation
2. diffs patterns - gitignore-style pattern validation
3. validate_llm_params - JSON object validation
4. content_override excluding the git inputs
"""

import os
import sys

import pytest

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from diff_analyzer import DEFAULT_DIFF_PATTERNS  # noqa: E402
from input_validation import (  # noqa: E402
    validate_content_override_mode,
    validate_diff_max_lines,
    validate_inputs,
    validate_llm_params,
)
from version import DEFAULT_TAG_PATTERN  # noqa: E402


@pytest.fixture
def git_dir(tmp_path, monkeypatch):
    """Run in a directory that looks like a git checkout."""
    (tmp_path / ".git").mkdir()
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestValidateDiffMaxLines:
    """Tests for validate_diff_max_lines function."""

    @pytest.mark.parametrize("value", ["0", "5000", "1000000", "", "   ", None])
    def test_valid(self, value):
        assert validate_diff_max_lines(value) == []

    def test_invalid_negative(self):
        errors = validate_diff_max_lines("-1")
        assert any("must be non-negative" in e for e in errors)

    @pytest.mark.parametrize("value", ["1.5", "lots"])
    def test_invalid_not_integer(self, value):
        errors = validate_diff_max_lines(value)
        assert any("must be an integer" in e for e in errors)


class TestValidateLlmParams:
    """Tests for validate_llm_params function."""

    @pytest.mark.parametrize("value", ["", '{"temperature": 0.2}', '{"thinking": {"type": "adaptive"}}'])
    def test_valid(self, value):
        assert validate_llm_params(value) == []

    def test_invalid_json(self):
        assert any("must be valid JSON" in e for e in validate_llm_params("{not json}"))

    def test_non_object(self):
        assert any("must be a JSON object" in e for e in validate_llm_params('["a"]'))


class TestDiffsPatterns:
    """diffs takes gitignore-style patterns, like context_files."""

    def test_default_patterns_valid(self, git_dir):
        result = validate_inputs(diffs=DEFAULT_DIFF_PATTERNS)
        assert result.valid, result.errors

    @pytest.mark.parametrize(
        "patterns",
        [
            "**/openapi*.yaml,**/migrations/**,**/*.proto",
            "**,!**/*.lock,!**/node_modules/**",
            "**/test_*.py,**/*_test.go,**/__tests__/**",
            "**/*.sql,**/db/migrations/*",
        ],
    )
    def test_real_world_patterns(self, git_dir, patterns):
        result = validate_inputs(diffs=patterns)
        assert result.valid, result.errors

    def test_path_traversal_rejected(self, git_dir):
        result = validate_inputs(diffs="../../etc/passwd")
        assert any("path traversal" in e.lower() for e in result.errors)

    def test_shell_characters_rejected(self, git_dir):
        result = validate_inputs(diffs="**/*.py;rm -rf /")
        assert not result.valid

    def test_all_errors_reported(self, git_dir):
        result = validate_inputs(diffs="../x", diff_max_lines="lots", llm_params="[]")
        assert len(result.errors) == 3


class TestContentOverrideMode:
    """content_override bypasses git, so git inputs set alongside it are rejected."""

    def test_defaults_allowed(self):
        assert validate_content_override_mode("", "HEAD", DEFAULT_TAG_PATTERN, DEFAULT_DIFF_PATTERNS) == []

    def test_unset_allowed(self):
        assert validate_content_override_mode(None, None, None, None) == []

    def test_disabling_diffs_allowed(self):
        assert validate_content_override_mode("", "HEAD", DEFAULT_TAG_PATTERN, "") == []

    def test_git_inputs_rejected(self):
        errors = validate_content_override_mode("v1.0.0", "main", "demo-*", "**/*.py")
        assert len(errors) == 1
        for name in ("base_ref", "head_ref", "tag_pattern", "diffs"):
            assert name in errors[0]

    def test_in_validate_inputs(self, tmp_path, monkeypatch):
        # No .git needed: the content replaces the repository
        monkeypatch.chdir(tmp_path)
        assert validate_inputs(content_override="## Repo\n### Features\n- item").valid
        result = validate_inputs(content_override="## Repo\n### Features\n- item", base_ref="v1.0.0")
        assert any("remove base_ref" in e for e in result.errors)
