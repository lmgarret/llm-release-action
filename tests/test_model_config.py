"""Tests for per-phase model resolution."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from model_config import ModelConfig  # noqa: E402


class TestModelResolution:
    def test_both_phases_fall_back_to_default(self):
        config = ModelConfig(default="anthropic/claude-sonnet-5")
        assert config.get_analysis_model() == "anthropic/claude-sonnet-5"
        assert config.get_changelog_model() == "anthropic/claude-sonnet-5"

    def test_analysis_override(self):
        config = ModelConfig(
            default="anthropic/claude-haiku-4-5",
            analysis="anthropic/claude-opus-5",
        )
        assert config.get_analysis_model() == "anthropic/claude-opus-5"
        assert config.get_changelog_model() == "anthropic/claude-haiku-4-5"

    def test_changelog_override(self):
        config = ModelConfig(
            default="anthropic/claude-haiku-4-5",
            changelog="anthropic/claude-sonnet-5",
        )
        assert config.get_analysis_model() == "anthropic/claude-haiku-4-5"
        assert config.get_changelog_model() == "anthropic/claude-sonnet-5"

    def test_both_overridden(self):
        config = ModelConfig(
            default="anthropic/claude-haiku-4-5",
            analysis="anthropic/claude-opus-5",
            changelog="anthropic/claude-sonnet-5",
        )
        assert config.get_analysis_model() == "anthropic/claude-opus-5"
        assert config.get_changelog_model() == "anthropic/claude-sonnet-5"


class TestFromEnv:
    def test_empty_overrides_are_treated_as_unset(self):
        # action.yml defaults model_analysis/model_changelog to '', so the
        # empty string must not become the model name.
        config = ModelConfig.from_env(
            model="anthropic/claude-sonnet-5",
            model_analysis="",
            model_changelog="",
        )
        assert config.analysis is None
        assert config.changelog is None
        assert config.get_analysis_model() == "anthropic/claude-sonnet-5"
        assert config.get_changelog_model() == "anthropic/claude-sonnet-5"

    def test_overrides_applied(self):
        config = ModelConfig.from_env(
            model="anthropic/claude-haiku-4-5",
            model_analysis="anthropic/claude-opus-5",
            model_changelog=None,
        )
        assert config.get_analysis_model() == "anthropic/claude-opus-5"
        assert config.get_changelog_model() == "anthropic/claude-haiku-4-5"
