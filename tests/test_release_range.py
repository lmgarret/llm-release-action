"""Tests for resolving the analyzed range and release name from git tags.

These use real git repositories, because the behaviour under test is how git
resolves refs and finds tags.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from input_validation import validate_inputs  # noqa: E402
from version import (  # noqa: E402
    SemanticVersion,
    detect_previous_tag,
    resolve_release_label,
    resolve_release_range,
)


def _run(cwd, *args):
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def _commit(cwd, message):
    (cwd / "f.txt").write_text(message)
    _run(cwd, "git", "add", "-A")
    _run(cwd, "git", "commit", "-q", "-m", message)
    return _run(cwd, "git", "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """History: v1.0.0, demo-202610010900, demo-202610080900, one untagged commit."""
    _run(tmp_path, "git", "init", "-q", ".")
    _run(tmp_path, "git", "config", "user.email", "test@example.com")
    _run(tmp_path, "git", "config", "user.name", "Test")
    _run(tmp_path, "git", "config", "tag.gpgsign", "false")
    _run(tmp_path, "git", "config", "commit.gpgsign", "false")

    _commit(tmp_path, "feat: first")
    _run(tmp_path, "git", "tag", "v1.0.0")
    _commit(tmp_path, "feat: second")
    _run(tmp_path, "git", "tag", "demo-202610010900")
    _commit(tmp_path, "fix: third")
    _run(tmp_path, "git", "tag", "demo-202610080900")
    _commit(tmp_path, "feat: fourth")

    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestDetectPreviousTag:
    def test_finds_nearest_matching_tag(self, repo):
        assert detect_previous_tag("demo-*", "HEAD") == "demo-202610080900"

    def test_skips_tag_on_head_itself(self, repo):
        # A run triggered by pushing a tag describes that tag's release
        _run(repo, "git", "tag", "demo-202610140900")
        assert detect_previous_tag("demo-*", "HEAD") == "demo-202610080900"
        assert detect_previous_tag("demo-*", "demo-202610140900") == "demo-202610080900"

    def test_none_when_nothing_matches(self, repo):
        assert detect_previous_tag("prod-*", "HEAD") is None


class TestResolveReleaseRangeNone:
    def test_detects_previous_tag_by_pattern(self, repo):
        result = resolve_release_range("none", "HEAD", tag_pattern="demo-*")
        assert result.base_ref == "demo-202610080900"
        assert result.version is None

    def test_any_tag_without_pattern(self, repo):
        assert resolve_release_range("none", "HEAD").base_ref == "demo-202610080900"

    def test_base_ref_can_be_a_sha(self, repo):
        sha = _run(repo, "git", "rev-parse", "v1.0.0")
        result = resolve_release_range("none", "HEAD", base_ref=sha)
        assert result.base_ref == sha
        assert result.version is None

    def test_error_when_no_tag_matches(self, repo):
        with pytest.raises(ValueError, match="No tag matching 'prod-\\*'"):
            resolve_release_range("none", "HEAD", tag_pattern="prod-*")


class TestResolveReleaseRangeSemver:
    def test_default_detects_latest_semver_tag(self, repo):
        result = resolve_release_range("semver", "HEAD")
        assert result.base_ref == "v1.0.0"
        assert result.version == SemanticVersion(1, 0, 0)

    def test_current_version_is_both_ref_and_version(self, repo):
        result = resolve_release_range("semver", "HEAD", current_version="v1.0.0")
        assert result.base_ref == "v1.0.0"
        assert result.version == SemanticVersion(1, 0, 0)

    def test_non_semver_base_ref_uses_nearest_semver_tag_for_version(self, repo):
        result = resolve_release_range("semver", "HEAD", base_ref="demo-202610080900")
        assert result.base_ref == "demo-202610080900"
        assert result.version == SemanticVersion(1, 0, 0)

    def test_current_version_overrides_derived_version(self, repo):
        result = resolve_release_range("semver", "HEAD", base_ref="demo-202610080900", current_version="v2.3.0")
        assert result.base_ref == "demo-202610080900"
        assert result.version == SemanticVersion(2, 3, 0)

    def test_tag_pattern_with_semver(self, repo):
        result = resolve_release_range("semver", "HEAD", tag_pattern="demo-*")
        assert result.base_ref == "demo-202610080900"
        assert result.version == SemanticVersion(1, 0, 0)

    def test_error_when_no_semver_tag_precedes_base(self, repo):
        _run(repo, "git", "tag", "-d", "v1.0.0")
        with pytest.raises(ValueError, match="versioning: none"):
            resolve_release_range("semver", "HEAD", base_ref="demo-202610080900")


class TestResolveReleaseLabel:
    def test_head_ref_tag(self, repo):
        assert resolve_release_label("demo-202610080900") == "demo-202610080900"

    def test_tag_on_head(self, repo):
        _run(repo, "git", "tag", "demo-202610140900")
        assert resolve_release_label("HEAD", "demo-*") == "demo-202610140900"

    def test_unreleased_otherwise(self, repo):
        assert resolve_release_label("HEAD", "demo-*") == "Unreleased"


class TestValidation:
    def test_accepts_timestamp_setup(self, repo):
        result = validate_inputs(versioning="none", base_ref="demo-202610080900", tag_pattern="demo-*")
        assert result.valid, result.errors

    def test_rejects_unknown_versioning(self, repo):
        result = validate_inputs(versioning="calver")
        assert any("Invalid versioning" in e for e in result.errors)

    def test_rejects_current_version_without_semver(self, repo):
        result = validate_inputs(versioning="none", current_version="v1.0.0")
        assert any("base_ref" in e for e in result.errors)

    @pytest.mark.parametrize("name", ["base_ref", "head_ref", "tag_pattern"])
    def test_rejects_option_like_refs(self, repo, name):
        result = validate_inputs(**{name: "--output=/tmp/x"})
        assert any("must not start with '-'" in e for e in result.errors)

    def test_rejects_whitespace_in_ref(self, repo):
        result = validate_inputs(base_ref="demo 1")
        assert not result.valid
