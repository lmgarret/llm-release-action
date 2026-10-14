"""Pytest configuration for DeepEval tests.

Environment variables:
- EVAL_MODEL: litellm model that judges output quality.
- TEST_MODEL: litellm model under test (analysis/changelog generation).
- EVAL_TEMPERATURE: sent as ``temperature`` on every eval call when set.
  Unset by default because many current models (Sonnet 5+, Opus 4.7+,
  Haiku 5.5) reject it. Parameters pass through as configured; a model that
  rejects one fails with the provider's error.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# Model configuration:
# - EVAL_MODEL: Sonnet 4.5 for judging output quality (smarter)
# - TEST_MODEL: Haiku 4.5 for analysis/changelog generation (what we're testing)
# See: https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html
DEFAULT_EVAL_MODEL = "bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0"
DEFAULT_TEST_MODEL = "bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0"


def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "eval: mark test as an LLM evaluation test")
    config.addinivalue_line("markers", "slow: mark test as slow (requires LLM calls)")


def get_eval_model() -> str:
    """Get model for evaluating outputs (should be smarter)."""
    return os.environ.get("EVAL_MODEL", DEFAULT_EVAL_MODEL)


def get_test_model() -> str:
    """Get model for generating outputs (what we're testing)."""
    return os.environ.get("TEST_MODEL", DEFAULT_TEST_MODEL)


def completion_kwargs(model: str, max_tokens: int) -> dict:
    """Build litellm.completion kwargs; adds temperature only if EVAL_TEMPERATURE is set."""
    kwargs = {"model": model, "max_tokens": max_tokens}
    temperature = os.environ.get("EVAL_TEMPERATURE")
    if temperature:
        kwargs["temperature"] = float(temperature)
    return kwargs
