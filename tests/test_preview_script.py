"""Tests for scripts/preview.py that do not need its dependencies installed."""

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_inline_dependencies_match_pyproject():
    """The script's PEP 723 block must list exactly the action's dependencies, plus typer."""
    script = (ROOT / "scripts" / "preview.py").read_text()
    match = re.search(r"# dependencies = \[\n(.*?)# \]", script, re.S)
    assert match, "PEP 723 dependencies block not found"
    inline = set(re.findall(r'"([^"]+)"', match.group(1))) - {"typer"}

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert inline == set(pyproject["project"]["dependencies"])
