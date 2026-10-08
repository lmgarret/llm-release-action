"""Tests for sanitizing generated changelogs and outputs."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import json

from analyze import sanitize_changelogs, set_output, write_changelog_files
from config import ChangelogConfig
from output_sanitizer import sanitize_changelog


class TestTextFormatsPassThrough:
    def test_markdown_is_unchanged(self) -> None:
        text = "- Generics: `Vec<T>` now implements <Display> [x](javascript:alert(1))"
        assert sanitize_changelog(text) == text

    def test_plain_is_unchanged(self) -> None:
        assert sanitize_changelog("a < b", output_format="plain") == "a < b"


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
        assert result == {"web": {"en": "<p>ok</p>"}, "dev": {"en": "<p>ok</p>"}}


class TestSetOutput:
    def test_multiline_value_cannot_forge_outputs(self, tmp_path, monkeypatch) -> None:
        output_file = tmp_path / "output"
        monkeypatch.setenv("GITHUB_OUTPUT", str(output_file))

        set_output("reasoning", "line one\nEOF_1700000000\nnext_version=9.9.9")

        content = output_file.read_text()
        delimiter = content.splitlines()[0].split("<<", 1)[1]
        assert content.count(delimiter) == 2
        assert content.endswith(f"\n{delimiter}\n")


class TestWriteChangelogFiles:
    def test_writes_one_file_per_audience_and_language(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
        config = ChangelogConfig.from_yaml(
            "web:\n  preset: customer\n  output_format: html\n  languages: [en, es]\n"
        )
        changelogs = {"web": {"en": "<p>hi</p>", "es": "<p>hola</p>"}, "default": {"en": "it's"}}

        paths = write_changelog_files(changelogs, config)

        assert paths["web"]["en"].endswith("web.en.html")
        assert paths["default"]["en"].endswith("default.en.md")
        for audience, by_language in changelogs.items():
            for language, text in by_language.items():
                path = paths[audience][language]
                assert path.startswith(str(tmp_path))
                with open(path, encoding="utf-8") as f:
                    assert f.read() == text
        json.dumps(paths)

    def test_each_run_gets_its_own_directory(self, tmp_path, monkeypatch) -> None:
        monkeypatch.setenv("RUNNER_TEMP", str(tmp_path))
        config = ChangelogConfig.from_yaml("")
        first = write_changelog_files({"default": {"en": "a"}}, config)
        second = write_changelog_files({"default": {"en": "b"}}, config)
        assert first["default"]["en"] != second["default"]["en"]
