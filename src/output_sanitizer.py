"""Prepare generated changelogs for output.

Markdown and plain-text changelogs are data: they pass through unchanged, and
escaping them is the job of whatever renders them. HTML output is different,
since the format exists to be inserted into a page as markup, so it keeps only
an allowlist of structural tags, with links restricted to safe schemes.
"""

import html
import re
from html.parser import HTMLParser
from typing import List, Tuple

MAX_CHANGELOG_BYTES = 65536

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


def sanitize_changelog(
    changelog: str,
    max_size: int = MAX_CHANGELOG_BYTES,
    output_format: str = "markdown",
) -> str:
    """Prepare a generated changelog for output.

    Args:
        changelog: LLM-generated changelog
        max_size: Maximum size in bytes; longer output is truncated
        output_format: "markdown", "plain" or "html"; only HTML is rewritten

    Returns:
        The changelog, size-limited, with HTML reduced to the allowlist
    """
    sanitized = _sanitize_html(changelog) if output_format == "html" else changelog

    if len(sanitized.encode("utf-8")) > max_size:
        while len(sanitized.encode("utf-8")) > max_size - 20:
            sanitized = sanitized[:-100]
        sanitized = sanitized.rstrip() + "\n\n... (truncated)"

    return sanitized
