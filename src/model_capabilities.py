"""Per-model parameter capabilities.

`model_config.py` decides *which* model each phase uses. This module decides
*what parameters that model accepts*.

Newer Anthropic models removed the sampling parameters: sending `temperature`,
`top_p` or `top_k` returns HTTP 400 ```temperature` is deprecated for this
model.``. LiteLLM cannot be relied on to drop them -- its
``AnthropicConfig.get_supported_openai_params()`` still reports `temperature` as
supported for these models, so ``drop_params=True`` is a no-op
(https://github.com/BerriAI/litellm/issues/26444).

The same generation of models also runs adaptive thinking by default, and
thinking tokens are drawn from ``max_tokens``. Small caps that were fine on
older models now return empty content, so those calls need a floor.
"""

import re
from typing import Optional

# Families that reject temperature / top_p / top_k with a 400.
# Matched against the normalized name on a version boundary, so a date- or
# point-suffixed variant matches but a different family never does.
NO_SAMPLING_PARAMS = (
    "claude-opus-5",
    "claude-opus-4-8",
    "claude-opus-4-7",
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-mythos-5",
)

# Families that run thinking by default when `thinking` is not sent at all.
# Note claude-opus-4-7/4-8 reject sampling params but run *without* thinking
# unless it is requested explicitly, so they are deliberately absent here.
THINKING_ON_BY_DEFAULT = (
    "claude-opus-5",
    "claude-sonnet-5",
    "claude-fable-5",
    "claude-mythos-5",
)

# Families that reject an explicit thinking={"type": "disabled"}.
NO_THINKING_OPT_OUT = (
    "claude-fable-5",
    "claude-mythos-5",
)

# Output-token floor for models where thinking will be on. Thinking tokens come
# out of max_tokens, so a small cap yields empty content rather than a short
# answer.
THINKING_MAX_TOKENS_FLOOR = 4096

# Bedrock cross-region inference prefixes, e.g.
# bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0
_REGION_PREFIXES = ("us.", "eu.", "apac.", "global.")

_VENDOR_PREFIXES = ("anthropic.",)

_VERSION_SUFFIX = re.compile(r"-v\d+:\d+$")


def normalize_model(model: str) -> str:
    """Reduce any LiteLLM model string to a bare family name.

    Handles the provider prefix, Bedrock region and vendor prefixes, the
    Bedrock ``-v1:0`` suffix and the Vertex ``@date`` separator.

    Examples:
        anthropic/claude-sonnet-5                            -> claude-sonnet-5
        bedrock/us.anthropic.claude-sonnet-4-5-20250929-v1:0 -> claude-sonnet-4-5-20250929
        vertex_ai/claude-opus-4-5@20251101                   -> claude-opus-4-5
        openai/gpt-4o-mini                                   -> gpt-4o-mini
    """
    name = model.strip().lower()

    # Drop the provider route: "bedrock/converse/us.anthropic.claude-..." keeps
    # only the final segment.
    name = name.rsplit("/", 1)[-1]

    # Vertex pins the snapshot with "@", not "-".
    name = name.split("@", 1)[0]

    for prefix in _REGION_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break

    for prefix in _VENDOR_PREFIXES:
        if name.startswith(prefix):
            name = name[len(prefix) :]
            break

    return _VERSION_SUFFIX.sub("", name)


def _matches_family(model: str, families: tuple) -> bool:
    """Match a normalized model name against families on a version boundary.

    ``claude-sonnet-5`` matches ``claude-sonnet-5`` and ``claude-sonnet-5-1``
    but never ``claude-sonnet-4-5-20250929``.
    """
    name = normalize_model(model)
    return any(name == family or name.startswith(family + "-") for family in families)


def is_anthropic(model: str) -> bool:
    """Whether this model string names an Anthropic Claude model."""
    return normalize_model(model).startswith("claude-")


def supports_sampling_params(model: str) -> bool:
    """Whether this model accepts temperature / top_p / top_k.

    Deny-list: unknown models keep the historical behaviour. Only the families
    known to return a 400 are excluded, so non-Anthropic providers and every
    older Claude are unaffected.
    """
    return not _matches_family(model, NO_SAMPLING_PARAMS)


def thinking_on_by_default(model: str) -> bool:
    """Whether this model thinks when `thinking` is omitted from the request."""
    return _matches_family(model, THINKING_ON_BY_DEFAULT)


def supports_thinking_opt_out(model: str) -> bool:
    """Whether this model accepts an explicit thinking={"type": "disabled"}."""
    return not _matches_family(model, NO_THINKING_OPT_OUT)


def thinking_enabled(model: str, thinking: str) -> bool:
    """Whether thinking will actually be on for this call.

    Args:
        model: LiteLLM model string
        thinking: the `thinking` input -- "", "adaptive" or "off"
    """
    if thinking == "adaptive":
        return True
    if thinking == "off":
        return False
    return thinking_on_by_default(model)


def min_max_tokens(model: str, thinking: str = "") -> int:
    """Output-token floor required for this model and thinking setting.

    Returns 0 when no floor applies.
    """
    return THINKING_MAX_TOKENS_FLOOR if thinking_enabled(model, thinking) else 0


def resolve_thinking_param(model: str, thinking: str) -> Optional[dict]:
    """Build the `thinking` request parameter, or None to omit it.

    Returns None when thinking is unset, the model is not Anthropic, or the
    model rejects an explicit opt-out.
    """
    if not thinking or not is_anthropic(model):
        return None
    if thinking == "adaptive":
        return {"type": "adaptive"}
    if thinking == "off" and supports_thinking_opt_out(model):
        return {"type": "disabled"}
    return None
