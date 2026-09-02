"""Tests for per-model parameter capabilities."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from model_capabilities import (  # noqa: E402
    THINKING_MAX_TOKENS_FLOOR,
    is_anthropic,
    min_max_tokens,
    normalize_model,
    resolve_thinking_param,
    supports_sampling_params,
    supports_thinking_opt_out,
    thinking_enabled,
    thinking_on_by_default,
)


class TestNormalizeModel:
    """Every LiteLLM model string form must reduce to a bare family name."""

    @pytest.mark.parametrize(
        "model,expected",
        [
            ("anthropic/claude-sonnet-5", "claude-sonnet-5"),
            ("claude-sonnet-5", "claude-sonnet-5"),
            (
                "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "claude-sonnet-4-5-20250929",
            ),
            (
                "bedrock/converse/us.anthropic.claude-opus-4-7-v1:0",
                "claude-opus-4-7",
            ),
            ("bedrock/eu.anthropic.claude-opus-5-v1:0", "claude-opus-5"),
            ("bedrock/apac.anthropic.claude-opus-5-v1:0", "claude-opus-5"),
            ("vertex_ai/claude-opus-4-5@20251101", "claude-opus-4-5"),
            ("openai/gpt-4o-mini", "gpt-4o-mini"),
            ("azure/my-deployment", "my-deployment"),
            ("  Anthropic/Claude-Sonnet-5  ", "claude-sonnet-5"),
        ],
    )
    def test_normalization(self, model, expected):
        assert normalize_model(model) == expected


class TestSamplingParams:
    """temperature/top_p/top_k are removed on a specific set of families."""

    @pytest.mark.parametrize(
        "model",
        [
            "anthropic/claude-opus-5",
            "anthropic/claude-opus-4-8",
            "anthropic/claude-opus-4-7",
            "anthropic/claude-sonnet-5",
            "anthropic/claude-fable-5",
            "claude-fable-5-1",
            "claude-mythos-5-1",
            "bedrock/us.anthropic.claude-sonnet-5-v1:0",
        ],
    )
    def test_rejected(self, model):
        assert supports_sampling_params(model) is False

    @pytest.mark.parametrize(
        "model",
        [
            "anthropic/claude-sonnet-4-6",
            "anthropic/claude-opus-4-6",
            "anthropic/claude-haiku-4-5",
            "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0",
            "bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0",
            "anthropic/claude-3-haiku-20240307",
            "openai/gpt-4o-mini",
            "gemini/gemini-2.0-flash",
        ],
    )
    def test_allowed(self, model):
        assert supports_sampling_params(model) is True

    @pytest.mark.parametrize(
        "model",
        [
            # A version-boundary match must not treat "-4-5" as "-5".
            "anthropic/claude-sonnet-4-5-20250929",
            "anthropic/claude-opus-4-5",
            # Nor a longer family name as a listed one.
            "anthropic/claude-sonnet-50",
        ],
    )
    def test_near_misses_are_not_matched(self, model):
        assert supports_sampling_params(model) is True

    def test_point_release_is_matched(self):
        # claude-fable-5-1 must inherit claude-fable-5's restrictions
        assert supports_sampling_params("claude-fable-5-1") is False


class TestThinking:
    """Thinking defaults differ across the families that reject sampling."""

    @pytest.mark.parametrize(
        "model", ["anthropic/claude-opus-5", "anthropic/claude-sonnet-5", "claude-fable-5-1"]
    )
    def test_on_by_default(self, model):
        assert thinking_on_by_default(model) is True

    @pytest.mark.parametrize(
        "model",
        [
            # These reject sampling params but do not think unless asked.
            "anthropic/claude-opus-4-7",
            "anthropic/claude-opus-4-8",
            "anthropic/claude-sonnet-4-5-20250929",
            "openai/gpt-4o-mini",
        ],
    )
    def test_off_by_default(self, model):
        assert thinking_on_by_default(model) is False

    def test_explicit_adaptive_overrides_default(self):
        assert thinking_enabled("anthropic/claude-opus-4-7", "adaptive") is True

    def test_explicit_off_overrides_default(self):
        assert thinking_enabled("anthropic/claude-sonnet-5", "off") is False

    def test_fable_rejects_opt_out(self):
        assert supports_thinking_opt_out("claude-fable-5-1") is False
        assert supports_thinking_opt_out("anthropic/claude-sonnet-5") is True

    @pytest.mark.parametrize(
        "model,thinking,expected",
        [
            ("anthropic/claude-sonnet-5", "adaptive", {"type": "adaptive"}),
            ("anthropic/claude-sonnet-5", "off", {"type": "disabled"}),
            ("anthropic/claude-sonnet-5", "", None),
            # Not Anthropic -- never send the parameter
            ("openai/gpt-4o-mini", "adaptive", None),
            # Fable rejects an explicit disable
            ("claude-fable-5-1", "off", None),
            ("claude-fable-5-1", "adaptive", {"type": "adaptive"}),
        ],
    )
    def test_resolve_thinking_param(self, model, thinking, expected):
        assert resolve_thinking_param(model, thinking) == expected


class TestMinMaxTokens:
    """Thinking tokens come out of max_tokens, so those models need a floor."""

    def test_floor_applied_when_thinking_on_by_default(self):
        assert min_max_tokens("anthropic/claude-sonnet-5") == THINKING_MAX_TOKENS_FLOOR

    def test_no_floor_for_older_model(self):
        assert min_max_tokens("bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0") == 0

    def test_no_floor_when_thinking_explicitly_off(self):
        assert min_max_tokens("anthropic/claude-sonnet-5", "off") == 0

    def test_floor_when_thinking_explicitly_on(self):
        assert min_max_tokens("anthropic/claude-opus-4-7", "adaptive") == (
            THINKING_MAX_TOKENS_FLOOR
        )

    def test_opus_4_7_has_no_floor_by_default(self):
        # Rejects sampling params, but does not think unless asked.
        assert min_max_tokens("anthropic/claude-opus-4-7") == 0


class TestIsAnthropic:
    @pytest.mark.parametrize(
        "model,expected",
        [
            ("anthropic/claude-sonnet-5", True),
            ("bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0", True),
            ("openai/gpt-4o-mini", False),
            ("gemini/gemini-2.0-flash", False),
        ],
    )
    def test_detection(self, model, expected):
        assert is_anthropic(model) is expected
