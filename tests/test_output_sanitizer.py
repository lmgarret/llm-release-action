"""Tests for sanitizing generated changelogs and outputs."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from analyze import sanitize_changelogs, set_output
from config import ChangelogConfig
from output_sanitizer import sanitize_changelog


class TestMarkdownSanitization:
    def test_strips_html_and_script_urls(self) -> None:
        result = sanitize_changelog("- Fix <img src=x onerror=alert(1)> [x](javascript:alert(1))")
        assert "<img" not in result
        assert "javascript:" not in result

    def test_neutralizes_data_links(self) -> None:
        result = sanitize_changelog("[x](data:text/html;base64,AAAA)")
        assert "data:" not in result

    def test_keeps_plain_words_ending_in_data(self) -> None:
        assert sanitize_changelog("- Export data: CSV and JSON") == "- Export data: CSV and JSON"

    def test_removes_bidi_overrides(self) -> None:
        assert "‮" not in sanitize_changelog("- Fix ‮gnp.exe")


class TestHtmlSanitization:
    def test_keeps_allowlisted_structure(self) -> None:
        html = "<h2>v1.2.0</h2>\n<ul>\n<li>OAuth: added</li>\n</ul>"
        assert sanitize_changelog(html, output_format="html") == html

    def test_drops_script_and_event_handlers(self) -> None:
        result = sanitize_changelog(
            '<script>alert(1)</script><li onclick="x()">Item</li><img src=x onerror=y>',
            output_format="html",
        )
        assert result == "<li>Item</li>"

    def test_filters_link_schemes(self) -> None:
        result = sanitize_changelog(
            '<a href="https://example.com/x">ok</a><a href="&#106;avascript:alert(1)">bad</a>',
            output_format="html",
        )
        assert result == '<a href="https://example.com/x">ok</a><a>bad</a>'

    def test_escapes_text(self) -> None:
        assert sanitize_changelog("<p>a < b & c</p>", output_format="html") == "<p>a &lt; b &amp; c</p>"


class TestSanitizeChangelogs:
    def test_uses_each_audience_format(self) -> None:
        config = ChangelogConfig.from_yaml(
            "web:\n  preset: customer\n  output_format: html\ndev:\n  preset: developer\n"
        )
        result = sanitize_changelogs(
            {"web": {"en": "<p>ok</p><script>x</script>"}, "dev": {"en": "<p>ok</p>"}},
            config,
        )
        assert result == {"web": {"en": "<p>ok</p>"}, "dev": {"en": "ok"}}


class TestSetOutput:
    def test_multiline_value_cannot_forge_outputs(self, tmp_path, monkeypatch) -> None:
        output_file = tmp_path / "output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        set_output("reasoning", "line one\nEOF_1700000000\nnext_version=9.9.9")

        content = output_file.read_text()
        delimiter = content.splitlines()[0].split("<<", 1)[1]
        assert content.count(delimiter) == 2
        assert content.endswith(f"\n{delimiter}\n")
