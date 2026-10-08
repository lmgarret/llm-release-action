"""Tests for enforcing validation.max_length during changelog generation."""

import sys
from pathlib import Path
from unittest.mock import patch

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analyze import run_phase2, run_phase3
from changelog import build_changelog_prompt, build_retry_prompt, get_length_budget
from config import AudienceConfig, ChangelogConfig, ValidationConfig, validate_changelog_config
from models import Change, ChangeCategory
from validation import truncate_to_length

CHANGES = [
    Change(id="1", category=ChangeCategory.FEATURE, title="Dark mode", description="Adds a dark theme"),
    Change(id="2", category=ChangeCategory.FIX, title="Sync crash", description="Fixes a crash during sync"),
]


def limited_config(max_length: int = 500, **validation) -> AudienceConfig:
    return AudienceConfig(
        name="store",
        preset="customer",
        output_format="plain",
        validation=ValidationConfig(max_length=max_length, **validation),
    )


def changelog_config(config: AudienceConfig) -> ChangelogConfig:
    return ChangelogConfig(audiences={config.name: config})


class TestLengthBudget:
    def test_no_budget_by_default(self) -> None:
        assert get_length_budget(AudienceConfig(name="test")) is None

    def test_budget_leaves_margin(self) -> None:
        assert get_length_budget(limited_config(500)) == 425

    def test_no_budget_when_validation_disabled(self) -> None:
        config = limited_config(500, enabled=False)
        assert get_length_budget(config) is None


class TestPrompts:
    def test_prompt_states_limit(self) -> None:
        prompt = build_changelog_prompt(CHANGES, limited_config(500), "en", "v1.2.0")
        assert "HARD LENGTH LIMIT: at most 425 characters" in prompt
        assert "Include ALL changes" not in prompt

    def test_prompt_without_limit_unchanged(self) -> None:
        prompt = build_changelog_prompt(CHANGES, AudienceConfig(name="test"), "en", "v1.2.0")
        assert "HARD LENGTH LIMIT" not in prompt
        assert "Include ALL changes" in prompt

    def test_retry_prompt_includes_errors_and_length(self) -> None:
        previous = "x" * 712
        prompt = build_retry_prompt("ORIGINAL", previous, ["Changelog too long (712 > 500 chars)"], limited_config(500))
        assert prompt.startswith("ORIGINAL")
        assert "- Changelog too long (712 > 500 chars)" in prompt
        assert "was 712 characters" in prompt
        assert "at most 425 characters" in prompt


class TestTruncateToLength:
    def test_short_content_untouched(self) -> None:
        assert truncate_to_length("## v1\n- a", 100) == "## v1\n- a"

    def test_cuts_at_line_boundary(self) -> None:
        content = "## v1.2.0\n- First item\n- Second item\n- Third item"
        result = truncate_to_length(content, 30)
        assert result == "## v1.2.0\n- First item"

    def test_drops_dangling_headers(self) -> None:
        content = "## v1.2.0\n- First item\n\n### Fixes\n- A long fix description here"
        result = truncate_to_length(content, 35)
        assert result == "## v1.2.0\n- First item"

    def test_single_long_line_cut_at_word(self) -> None:
        content = "This release adds a dark theme and fixes a crash during sync"
        result = truncate_to_length(content, 20)
        assert len(result) <= 20
        assert result == "This release adds a…"


class TestConfigValidation:
    def test_rejects_invalid_max_length(self) -> None:
        errors = validate_changelog_config({"store": {"validation": {"max_length": 0}}})
        assert any("max_length" in e for e in errors)

    def test_rejects_negative_max_retries(self) -> None:
        errors = validate_changelog_config({"store": {"validation": {"max_retries": -1}}})
        assert any("max_retries" in e for e in errors)


class TestPhase2Retry:
    def run(self, responses, config: AudienceConfig):
        prompts = []

        def fake_llm(**kwargs):
            prompts.append(kwargs["prompt"])
            return responses[len(prompts) - 1], None

        with patch("analyze.call_llm_with_retry", side_effect=fake_llm):
            changelogs, _ = run_phase2(
                model="test",
                changes=CHANGES,
                changelog_config=changelog_config(config),
                version="v1.2.0",
                base_url=None,
                temperature=None,
                max_tokens=1000,
                timeout=10,
                debug=False,
            )
        return changelogs[config.name]["en"], prompts

    def test_retries_until_within_limit(self) -> None:
        too_long = "Dark mode is here and a sync crash is fixed. " * 20
        fits = "Dark mode is here, and a crash during sync is fixed. Enjoy the new theme!"
        result, prompts = self.run([too_long, fits], limited_config(200))
        assert result == fits
        assert len(prompts) == 2
        assert "Changelog too long" in prompts[1]

    def test_stops_after_max_retries(self) -> None:
        too_long = "Dark mode is here and a sync crash is fixed. " * 20
        result, prompts = self.run([too_long] * 3, limited_config(200, max_retries=2))
        assert len(prompts) == 3
        assert result == too_long.strip()

    def test_no_retry_when_on_failure_is_warn(self) -> None:
        too_long = "Dark mode is here and a sync crash is fixed. " * 20
        _, prompts = self.run([too_long], limited_config(200, on_failure="warn"))
        assert len(prompts) == 1


class TestPhase3Truncation:
    def test_truncates_after_retries(self) -> None:
        config = limited_config(60)
        changelog = "Dark mode is here.\nA crash during sync is fixed.\nThe app starts faster on old phones."
        result = run_phase3({"store": {"en": changelog}}, CHANGES, changelog_config(config), "v1.2.0")
        assert result["store"]["en"] == "Dark mode is here.\nA crash during sync is fixed."

    def test_default_limit_does_not_truncate(self) -> None:
        config = AudienceConfig(name="dev", preset="developer")
        changelog = "## v1.2.0\n\n### Features\n- Dark mode: Adds a dark theme\n" * 3
        result = run_phase3({"dev": {"en": changelog}}, CHANGES, changelog_config(config), "v1.2.0")
        assert result["dev"]["en"] == changelog
