"""Sanitize LLM-generated text before it leaves the action as an output.

Changelogs end up in release notes, PR comments and web pages, and the text
that produced them may have been steered by a malicious commit or file. Markdown
and plain-text output loses all HTML; HTML output keeps only an allowlist of
structural tags, with links restricted to safe schemes.
"""

import html
import re
from html.parser import HTMLParser
from typing import List, Tuple

MAX_CHANGELOG_BYTES = 65536

# Bidi overrides/isolates and C0 controls (except tab and newline) can hide or
# reorder text when rendered.
_HIDDEN = re.compile(r"[‪-‮⁦-⁩\x00-\x08\x0b-\x1f\x7f]")

_SCRIPT_SCHEME = re.compile(r"(?i)\b(?:javascript|vbscript)\s*:[^\s\"']*")
_MARKDOWN_DATA_LINK = re.compile(r"(?i)(\]\(\s*)data\s*:[^)\s]*")

_ALLOWED_TAGS = {
    "a", "b", "blockquote", "br", "code", "em", "h1", "h2", "h3", "h4", "h5",
    "h6", "hr", "i", "li", "ol", "p", "pre", "strong", "ul",
}
_VOID_TAGS = {"br", "hr"}
_DROP_CONTENT_TAGS = {
    "embed", "iframe", "noscript", "object", "script", "style", "template",
    "textarea", "title",
}
_SAFE_HREF = re.compile(r"(?i)^(?:https?://|mailto:|#|/)")


class _AllowlistSanitizer(HTMLParser):
    """Rebuild HTML from allowlisted tags only, escaping all text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: List[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, str]]) -> None:
        if tag in _DROP_CONTENT_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth or tag not in _ALLOWED_TAGS:
            return
        if tag == "a":
            href = (dict(attrs).get("href") or "").strip()
            if _SAFE_HREF.match(href):
                self.parts.append(f'<a href="{html.escape(href, quote=True)}">')
            else:
                self.parts.append("<a>")
            return
        self.parts.append(f"<{tag}>")

    def handle_endtag(self, tag: str) -> None:
        if tag in _DROP_CONTENT_TAGS:
            self._skip_depth = max(0, self._skip_depth - 1)
            return
        if self._skip_depth or tag not in _ALLOWED_TAGS or tag in _VOID_TAGS:
            return
        self.parts.append(f"</{tag}>")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(html.escape(data, quote=False))


def _sanitize_html(text: str) -> str:
    parser = _AllowlistSanitizer()
    parser.feed(text)
    parser.close()
    return "".join(parser.parts)


def _sanitize_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = _SCRIPT_SCHEME.sub("", text)
    return _MARKDOWN_DATA_LINK.sub(r"\1#", text)


def sanitize_changelog(
    changelog: str,
    max_size: int = MAX_CHANGELOG_BYTES,
    output_format: str = "markdown",
) -> str:
    """Sanitize a generated changelog for its output format.

    Args:
        changelog: LLM-generated changelog
        max_size: Maximum size in bytes; longer output is truncated
        output_format: "markdown", "plain" or "html"

    Returns:
        Sanitized changelog
    """
    sanitized = _HIDDEN.sub("", changelog)

    if output_format == "html":
        sanitized = _sanitize_html(sanitized)
    else:
        sanitized = _sanitize_text(sanitized)

    if len(sanitized.encode("utf-8")) > max_size:
        while len(sanitized.encode("utf-8")) > max_size - 20:
            sanitized = sanitized[:-100]
        sanitized = sanitized.rstrip() + "\n\n... (truncated)"

    return sanitized
