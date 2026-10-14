"""Tests for audience instructions, header/footer framing and issue links."""

import sys
from pathlib import Path

import pytest

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analyzer import keep_verified_issues, parse_change_line
from changelog import add_frames, build_changelog_prompt, reserve_frame_length
from config import AudienceConfig, ChangelogConfig, ValidationConfig, validate_changelog_config
from flatten import build_flatten_prompt
from models import Change, ChangeCategory
from prompt_builder import build_semantic_analysis_prompt

COMMITS = """1. abc1234: feat: chat upload (#12)

Fixes ABC-252
2. def5678: Merge pull request #13 from acme/dev/abc-301-pdf-preview"""


def change(**kwargs) -> Change:
    return Change(id="1", category=ChangeCategory.FEATURE, title="PDF upload", description="Upload PDFs", **kwargs)


class TestIssueExtraction:
    def test_prompts_ask_for_issues(self) -> None:
        assert "issues:ABC-123" in build_flatten_prompt("x")
        prompt = build_semantic_analysis_prompt(commits=[], base_version="v1.0.0", content_override="- x")
        assert "issues:ABC-123" in prompt

    def test_parse_issues(self) -> None:
        result = parse_change_line("[feature|high] Upload | PDFs | commits:abc1234 | issues:ABC-252, ABC-301", 0)
        assert result is not None
        assert result.issues == ["ABC-252", "ABC-301"]
        assert result.commits == ["abc1234"]

    def test_keeps_ids_found_in_commits(self) -> None:
        changes = [change(issues=["ABC-252", "ABC-301", "ABC-252"])]
        keep_verified_issues(changes, COMMITS)
        # ABC-301 only appears lowercase, in a branch name
        assert changes[0].issues == ["ABC-252", "ABC-301"]

    @pytest.mark.parametrize(
        "issue",
        [
            "ABC-999",  # invented
            "ABC-25",  # prefix of a real ID
            "BC-252",  # suffix of a real ID
            "Fixes",  # no digit
            "ABC-252](javascript:alert(1))",  # not a plain ID
        ],
    )
    def test_drops_unverified_ids(self, issue: str) -> None:
        changes = [change(issues=[issue])]
        keep_verified_issues(changes, COMMITS + "\n3. 0123abc: Fixes ABC-252](javascript:alert(1))")
        assert changes[0].issues == []


class TestIssueLinks:
    def prompt(self, **config) -> str:
        return build_changelog_prompt(
            [change(issues=["ABC-252"])], AudienceConfig(name="team", **config), language="en", version="v1.1.0"
        )

    def test_linked_with_template(self) -> None:
        prompt = self.prompt(link_issues=True, issue_url_template="https://linear.app/acme/issue/{id}")
        assert "Issues: [ABC-252](https://linear.app/acme/issue/ABC-252)" in prompt
        assert "copied exactly as given in the Issues line" in prompt

    def test_plain_ids_without_template(self) -> None:
        assert "Issues: ABC-252" in self.prompt(link_issues=True)

    def test_hidden_without_link_issues(self) -> None:
        assert "ABC-252" not in self.prompt(issue_url_template="https://linear.app/acme/issue/{id}")

    @pytest.mark.parametrize("template", ["linear.app/acme/issue/{id}", "https://linear.app/acme/issue/", 42])
    def test_invalid_template(self, template) -> None:
        errors = validate_changelog_config({"team": {"issue_url_template": template}})
        assert any("issue_url_template" in e for e in errors)


class TestInstructions:
    def test_added_to_prompt(self) -> None:
        config = AudienceConfig(name="team", instructions="Start with a one-line summary.")
        prompt = build_changelog_prompt([change()], config, language="en", version="v1.1.0")
        assert "## Maintainer Instructions" in prompt
        assert "Start with a one-line summary." in prompt

    def test_absent_by_default(self) -> None:
        prompt = build_changelog_prompt([change()], AudienceConfig(name="team"), language="en", version="v1.1.0")
        assert "Maintainer Instructions" not in prompt

    def test_too_long(self) -> None:
        errors = validate_changelog_config({"team": {"instructions": "x" * 4001}})
        assert errors == ["team: instructions must be at most 4000 characters"]


class TestFrames:
    def config(self, **kwargs) -> ChangelogConfig:
        return ChangelogConfig(audiences={"team": AudienceConfig(name="team", **kwargs)})

    def test_header_and_footer_wrap_changelog(self) -> None:
        config = self.config(
            header="Release [{version}](https://linear.app/r/{version})", footer="Since {previous_version}"
        )
        framed = add_frames({"team": {"en": "## Features\n- PDF upload\n"}}, config, "v1.1.0", "v1.0.0")
        assert framed["team"]["en"] == (
            "Release [v1.1.0](https://linear.app/r/v1.1.0)\n\n## Features\n- PDF upload\n\nSince v1.0.0"
        )

    def test_no_frame_leaves_changelog(self) -> None:
        framed = add_frames({"team": {"en": "## Features"}, "other": {"en": "x"}}, self.config(), "v1", "v0")
        assert framed == {"team": {"en": "## Features"}, "other": {"en": "x"}}

    def test_reserves_length_for_frame(self) -> None:
        config = self.config(header="Release {version}", footer="Bye", validation=ValidationConfig(max_length=500))
        reserved = reserve_frame_length(config, "v1.1.0", "v1.0.0")
        # "Release v1.1.0" + "\n\n" and "Bye" + "\n\n"
        assert reserved.audiences["team"].validation.max_length == 500 - 16 - 5

        framed = add_frames({"team": {"en": "x" * 479}}, reserved, "v1.1.0", "v1.0.0")
        assert len(framed["team"]["en"]) == 500

    def test_default_max_length_untouched(self) -> None:
        config = self.config(header="Release {version}")
        reserved = reserve_frame_length(config, "v1.1.0", "v1.0.0")
        assert reserved.audiences["team"].validation.max_length == ValidationConfig().max_length

    def test_rejected_for_json(self) -> None:
        errors = validate_changelog_config({"team": {"header": "Hi", "output_format": "json"}})
        assert errors == ["team: header and footer are not supported with output_format json"]
