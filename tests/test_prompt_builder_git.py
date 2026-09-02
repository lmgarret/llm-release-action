"""Tests for the git-facing helpers in prompt_builder.

These exercise real git repositories rather than mocks, because the behaviour
under test is how git itself resolves refs.
"""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prompt_builder import get_commits, ref_exists  # noqa: E402


def _run(cwd, *args):
    subprocess.run(args, cwd=cwd, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A git repo with three commits, a v0.1.0 tag, then one more commit."""
    _run(tmp_path, "git", "init", "-q", ".")
    _run(tmp_path, "git", "config", "user.email", "test@example.com")
    _run(tmp_path, "git", "config", "user.name", "Test")

    for message in ("feat: first thing", "fix: second thing", "feat!: breaking thing"):
        (tmp_path / "f.txt").write_text(message)
        _run(tmp_path, "git", "add", "-A")
        _run(tmp_path, "git", "commit", "-q", "-m", message)

    _run(tmp_path, "git", "tag", "v0.1.0")

    (tmp_path / "g.txt").write_text("after")
    _run(tmp_path, "git", "add", "-A")
    _run(tmp_path, "git", "commit", "-q", "-m", "chore: after the tag")

    # get_commits shells out to git in the cwd
    monkeypatch.chdir(tmp_path)
    return tmp_path


class TestRefExists:
    def test_existing_tag(self, repo):
        assert ref_exists("v0.1.0") is True

    def test_head(self, repo):
        assert ref_exists("HEAD") is True

    def test_missing_tag(self, repo):
        assert ref_exists("v0.0.0") is False

    def test_garbage_ref(self, repo):
        assert ref_exists("not-a-ref-at-all") is False

    def test_does_not_raise_outside_a_repo(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        assert ref_exists("v1.0.0") is False


class TestGetCommits:
    def test_range_from_existing_tag(self, repo):
        commits = get_commits("v0.1.0", "HEAD")
        assert len(commits) == 1
        assert "after the tag" in commits[0].message

    def test_missing_base_falls_back_to_full_history(self, repo):
        # The first-release case: the release workflow passes a synthetic
        # v0.0.0 when no tag exists yet, which is a valid version but not a
        # valid ref. Previously this raised
        # "fatal: ambiguous argument 'v0.0.0..HEAD'".
        commits = get_commits("v0.0.0", "HEAD")
        assert len(commits) == 4
        messages = " ".join(c.message for c in commits)
        assert "first thing" in messages
        assert "after the tag" in messages

    def test_fallback_still_detects_breaking_markers(self, repo):
        commits = get_commits("v0.0.0", "HEAD")
        breaking = [c for c in commits if c.has_breaking_marker]
        assert len(breaking) == 1
        assert "breaking thing" in breaking[0].message

    def test_fallback_announces_itself(self, repo, capsys):
        get_commits("v0.0.0", "HEAD")
        output = capsys.readouterr().out
        assert "does not exist" in output
        assert "first release" in output

    def test_no_announcement_on_the_normal_path(self, repo, capsys):
        get_commits("v0.1.0", "HEAD")
        assert capsys.readouterr().out == ""

    def test_commit_hashes_are_short(self, repo):
        for commit in get_commits("v0.0.0", "HEAD"):
            assert len(commit.hash) == 8
