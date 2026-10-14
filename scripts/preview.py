#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "typer",
#     "litellm==1.103.0",
#     "boto3==1.43.103",
#     "pyyaml>=6.0.3",
#     "langcodes>=3.5.1",
#     "language-data>=1.4.0",
#     "langdetect>=1.0.9",
#     "jinja2>=3.1.6",
#     "regex>=2026.9.10",
#     "pathspec>=1.1.1",
#     "unidiff>=1.0.1",
# ]
# ///
"""Preview the changelogs the action would generate for a repo, without GitHub.

Runs the same pipeline as the action against a local checkout and prints each
audience/language changelog. Save Phase 1 output with --save-changes, then pass
it back with --changes to iterate on changelog_config without re-analyzing.
"""

import contextlib
import dataclasses
import io
import json
import os
import sys
import tempfile
from enum import Enum
from pathlib import Path
from typing import Annotated, Any, NoReturn

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

SRC_DIR = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_DIR))

import analyze  # noqa: E402
from config import ChangelogConfig  # noqa: E402
from model_config import ModelConfig  # noqa: E402
from models import AnalysisResult, BreakingInfo, Change, ChangeCategory, Importance  # noqa: E402
from prompt_builder import ref_exists  # noqa: E402
from repo_url import get_repository_url  # noqa: E402

app = typer.Typer(add_completion=False, help=__doc__)
# Bound to the real streams so output survives the log capture below
console = Console(file=sys.stdout)
err_console = Console(file=sys.stderr)


@dataclasses.dataclass
class Preview:
    """Everything shown to the user after a run."""

    bump: str
    current_version: str
    next_version: str
    release_name: str
    project_type: str
    reasoning: str
    changelogs: dict[str, dict[str, str]]
    warnings: list[str]
    usage: dict[str, Any]
    changes: list[Change]


# --- Inputs -----------------------------------------------------------------


def parse_extra_inputs(pairs: list[str]) -> dict[str, str]:
    """Turn ["max_tokens=8000", ...] into {"max_tokens": "8000", ...}."""
    inputs = {}
    for pair in pairs:
        name, sep, value = pair.partition("=")
        if not sep or not name:
            fail(f"--input expects NAME=VALUE, got {pair!r}")
        inputs[name.strip().lower()] = value
    return inputs


def set_action_inputs(inputs: dict[str, str]) -> None:
    """Expose inputs the way the action does, as INPUT_* environment variables."""
    for name, value in inputs.items():
        os.environ[f"INPUT_{name.upper()}"] = value


def read_config(path: Path | None) -> str:
    """Return the changelog_config YAML, or "" for the action's default audience."""
    if path is None:
        return ""
    if not path.is_file():
        fail(f"no such config file: {path}")
    return path.read_text(encoding="utf-8")


# --- Changes (de)serialization ---------------------------------------------


def to_jsonable(value: Any) -> Any:
    """Convert enums nested in asdict() output to their values."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_jsonable(v) for v in value]
    return value


def change_from_dict(data: dict[str, Any]) -> Change:
    """Rebuild a Change saved with --save-changes."""
    data = dict(data)
    data["category"] = ChangeCategory(data["category"])
    data["importance"] = Importance(data["importance"])
    if data.get("breaking"):
        data["breaking"] = BreakingInfo(**data["breaking"])
    return Change(**data)


def save_changes(preview: Preview, path: Path) -> None:
    """Write Phase 1 output so a later run can skip straight to Phase 2."""
    payload = {
        "bump": preview.bump,
        "current_version": preview.current_version,
        "next_version": preview.next_version,
        "release_name": preview.release_name,
        "project_type": preview.project_type,
        "reasoning": preview.reasoning,
        "changes": [to_jsonable(dataclasses.asdict(c)) for c in preview.changes],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def release_name_of(saved: dict[str, Any]) -> str:
    """Release name in a saved changes file (older files only have next_version)."""
    return saved.get("release_name") or saved["next_version"]


def load_changes(path: Path) -> dict[str, Any]:
    """Read a file written by --save-changes."""
    if not path.is_file():
        fail(f"no such changes file: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["changes"] = [change_from_dict(c) for c in payload["changes"]]
    return payload


# --- Running the pipeline ---------------------------------------------------


def parse_github_output(text: str) -> dict[str, str]:
    """Parse a GITHUB_OUTPUT file (name=value and name<<DELIM heredocs)."""
    outputs: dict[str, str] = {}
    lines = iter(text.splitlines())
    for line in lines:
        if "<<" in line and ("=" not in line or line.index("<<") < line.index("=")):
            name, delimiter = line.split("<<", 1)
            body = []
            for body_line in lines:
                if body_line == delimiter:
                    break
                body.append(body_line)
            outputs[name] = "\n".join(body)
        elif "=" in line:
            name, value = line.split("=", 1)
            outputs[name] = value
    return outputs


@contextlib.contextmanager
def captured_logs(verbose: bool):
    """Hide the action's GitHub-style logs unless --verbose; keep them for errors."""
    if verbose:
        yield io.StringIO()
        return
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        yield buffer


def report_failure(logs: str) -> NoReturn:
    """Show the action's error lines (or the log tail) and exit."""
    errors = [line.removeprefix("::error::") for line in logs.splitlines() if line.startswith("::error::")]
    detail = "\n".join(errors) or "\n".join(logs.splitlines()[-20:])
    err_console.print(Panel(detail or "no log output", title="[red]Analysis failed", border_style="red"))
    raise typer.Exit(1)


def run_full(verbose: bool) -> Preview:
    """Run the action's main() end to end and collect its outputs."""
    captured: list[AnalysisResult] = []
    original_phase1 = analyze.run_phase1

    def capturing_phase1(*args: Any, **kwargs: Any) -> AnalysisResult:
        result = original_phase1(*args, **kwargs)
        captured.append(result)
        return result

    with tempfile.TemporaryDirectory() as tmp:
        output_file = Path(tmp) / "github_output"
        os.environ["GITHUB_OUTPUT"] = str(output_file)
        os.environ["RUNNER_TEMP"] = tmp
        analyze.run_phase1 = capturing_phase1
        with console.status("Analyzing commits and generating changelogs…"), captured_logs(verbose) as logs:
            exit_code = analyze.main()
        analyze.run_phase1 = original_phase1
        if exit_code != 0:
            report_failure(logs.getvalue())
        outputs = parse_github_output(output_file.read_text(encoding="utf-8"))

    return Preview(
        bump=outputs["bump"],
        current_version=outputs["current_version"],
        next_version=outputs["next_version"],
        release_name=outputs.get("release_name") or outputs["next_version"],
        project_type=outputs["project_type"],
        reasoning=outputs.get("reasoning", ""),
        changelogs=json.loads(outputs["changelogs"]),
        warnings=json.loads(outputs.get("warnings", "[]")),
        usage=json.loads(outputs.get("usage", "{}")),
        changes=captured[0].changes if captured else [],
    )


def generate_changelogs(saved: dict[str, Any], config_yaml: str) -> dict[str, dict[str, str]]:
    """Phases 2 and 3 plus sanitizing, with the same settings main() reads."""
    model_config = ModelConfig.from_env(
        model=analyze.get_env("INPUT_MODEL"),
        model_analysis=None,
        model_changelog=os.environ.get("INPUT_MODEL_CHANGELOG") or None,
    )
    changelog_config = ChangelogConfig.from_yaml(config_yaml)
    changelogs, _ = analyze.run_phase2(
        model=model_config.get_changelog_model(),
        changes=saved["changes"],
        changelog_config=changelog_config,
        version=release_name_of(saved),
        base_url=get_repository_url(),
        temperature=analyze.get_env_optional_float("INPUT_TEMPERATURE", None),
        max_tokens=analyze.get_env_int("INPUT_MAX_TOKENS", 4000),
        timeout=analyze.get_env_int("INPUT_TIMEOUT", 120),
        debug=analyze.get_env_bool("INPUT_DEBUG", False),
        thinking=os.environ.get("INPUT_THINKING", "").strip().lower(),
        extra_params=analyze.parse_extra_llm_params(os.environ.get("INPUT_EXTRA_LLM_PARAMS", "")),
        project_type=saved["project_type"],
    )
    if changelogs:
        changelogs = analyze.run_phase3(
            changelogs=changelogs,
            changes=saved["changes"],
            changelog_config=changelog_config,
            version=release_name_of(saved),
        )
    return analyze.sanitize_changelogs(changelogs, changelog_config)


def run_changelogs_only(saved: dict[str, Any], config_yaml: str, verbose: bool) -> Preview:
    """Regenerate changelogs from saved Phase 1 changes, skipping the analysis."""
    error: Exception | None = None
    with console.status("Generating changelogs from saved changes…"), captured_logs(verbose) as logs:
        try:
            changelogs = generate_changelogs(saved, config_yaml)
        except Exception as e:  # noqa: BLE001 - surface any pipeline error to the user
            error = e
    if error is not None:
        report_failure(f"{logs.getvalue()}\n::error::{error}")

    return Preview(
        bump=saved["bump"],
        current_version=saved["current_version"],
        next_version=saved["next_version"],
        release_name=release_name_of(saved),
        project_type=saved["project_type"],
        reasoning=saved.get("reasoning", ""),
        changelogs=changelogs,
        warnings=[],
        usage=analyze._usage.to_dict(),
        changes=saved["changes"],
    )


# --- Rendering --------------------------------------------------------------


def render_summary(preview: Preview, from_saved: bool) -> Table:
    """Version, project type and token usage at a glance."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="bold cyan")
    table.add_column()
    source = " (from saved changes)" if from_saved else ""
    table.add_row("Release", f"{preview.current_version} → {preview.release_name}{source}")
    table.add_row("Next version", preview.next_version or "— (versioning: none)")
    table.add_row("Bump", preview.bump)
    table.add_row("Project type", preview.project_type)
    table.add_row("Changes", str(len(preview.changes)))
    for model, stats in preview.usage.items():
        tokens = stats["input_tokens"] + stats["output_tokens"]
        table.add_row("Tokens", f"{tokens:,} in {stats['calls']} calls ({model})")
    return table


def render_changelogs(changelogs: dict[str, dict[str, str]], raw: bool) -> None:
    """Print one panel per audience/language."""
    for audience, by_language in changelogs.items():
        for language, text in by_language.items():
            body = text if raw else Markdown(text)
            console.print(Panel(body, title=f"[bold]{audience}[/] · {language}", subtitle=f"{len(text)} chars"))


def write_changelogs(changelogs: dict[str, dict[str, str]], out_dir: Path) -> int:
    """Write <audience>.<language>.md files and return how many were written."""
    out_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    for audience, by_language in changelogs.items():
        for language, text in by_language.items():
            (out_dir / f"{audience}.{language}.md").write_text(text, encoding="utf-8")
            count += 1
    return count


def fail(message: str) -> NoReturn:
    """Print an error and exit."""
    err_console.print(f"[red]Error:[/] {message}")
    raise typer.Exit(1)


# --- CLI --------------------------------------------------------------------


@app.command()
def main(
    model: Annotated[
        str, typer.Option(help="LiteLLM model string, e.g. anthropic/claude-sonnet-5-5.", envvar="LLM_RELEASE_MODEL")
    ],
    repo: Annotated[Path, typer.Option(help="Checkout of the repo to analyze.")] = Path("."),
    base: Annotated[
        str | None, typer.Option("--from", help="Tag, SHA or branch to compare from. Default: previous release tag.")
    ] = None,
    head: Annotated[str, typer.Option("--to", help="Ref to compare to.")] = "HEAD",
    versioning: Annotated[str, typer.Option(help="semver, or none for non-semver (e.g. timestamped) tags.")] = "semver",
    tag_pattern: Annotated[str, typer.Option(help="Glob matching release tags, e.g. 'demo-*'.")] = "",
    config: Annotated[Path | None, typer.Option(help="changelog_config YAML file.")] = None,
    project_type: Annotated[str, typer.Option(help="auto, library, api, service, app or generic.")] = "auto",
    context_files: Annotated[str, typer.Option(help="context_files patterns, e.g. README.md,docs/glossary.md.")] = "",
    inputs: Annotated[
        list[str] | None, typer.Option("--input", help="Any other action input as NAME=VALUE (repeatable).")
    ] = None,
    save_changes_to: Annotated[
        Path | None, typer.Option("--save-changes", help="Save Phase 1 changes to this JSON file.")
    ] = None,
    changes_file: Annotated[
        Path | None, typer.Option("--changes", help="Reuse saved changes; only regenerate changelogs.")
    ] = None,
    out_dir: Annotated[Path | None, typer.Option(help="Also write <audience>.<language>.md files here.")] = None,
    raw: Annotated[bool, typer.Option(help="Print markdown source instead of rendering it.")] = False,
    verbose: Annotated[bool, typer.Option(help="Show the action's own logs.")] = False,
) -> None:
    """Preview changelogs for REPO between --from and --to using a changelog config."""
    config_yaml = read_config(config.resolve() if config else None)
    saved = load_changes(changes_file.resolve()) if changes_file else None
    save_path = save_changes_to.resolve() if save_changes_to else None
    out_path = out_dir.resolve() if out_dir else None
    if not repo.is_dir():
        fail(f"no such directory: {repo}")
    os.chdir(repo)
    # The action treats a missing base ref as a first release and analyzes the
    # whole history; in a preview that is almost always a typo, and costly.
    if base and not saved and not ref_exists(base):
        fail(f"--from {base!r} is not a ref in {repo}")

    set_action_inputs(
        {
            "model": model,
            "base_ref": base or "",
            "head_ref": head,
            "versioning": versioning,
            "tag_pattern": tag_pattern,
            "changelog_config": config_yaml,
            "project_type": project_type,
            "context_files": context_files,
            **parse_extra_inputs(inputs or []),
        }
    )

    preview = run_changelogs_only(saved, config_yaml, verbose) if saved else run_full(verbose)

    console.print(render_summary(preview, from_saved=saved is not None))
    for warning in preview.warnings:
        console.print(f"[yellow]Warning:[/] {warning}")
    render_changelogs(preview.changelogs, raw)

    if save_path and not saved:
        save_changes(preview, save_path)
        console.print(f"[green]Saved {len(preview.changes)} changes to[/] {save_path}")
    if out_path:
        count = write_changelogs(preview.changelogs, out_path)
        console.print(f"[green]Wrote {count} changelog file(s) to[/] {out_path}")


if __name__ == "__main__":
    app()
