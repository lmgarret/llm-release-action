"""Core diff analysis module for parsing and prioritizing git diffs.

This module parses unified diffs, applies exclusion patterns, prioritizes
files by importance, and extracts structured changes using LLM.

Features:
- Unified diff parsing (via unidiff library)
- Gitignore-style file selection (via pathspec)
- Priority-based file ordering (API specs > migrations > config > other)
- Line budget with warnings
- LLM-based change extraction with structured output
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

import pathspec
from pathspec.patterns.gitignore.spec import GitIgnoreSpecPattern
from unidiff import PatchSet

from summarizing_map_reduce import estimate_tokens
from untrusted import UNTRUSTED_NOTICE, wrap


@dataclass
class FileDiff:
    """Represents a parsed file diff."""

    path: str
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    is_binary: bool = False
    is_rename: bool = False
    old_path: str = ""

    @property
    def line_count(self) -> int:
        """Total number of changed lines."""
        return len(self.added_lines) + len(self.removed_lines)


@dataclass
class DiffAnalysisResult:
    """Result of diff analysis."""

    extracted_changes: str
    diffs_processed: int
    total_lines: int
    warnings: list[str] = field(default_factory=list)


# Files whose diffs are analyzed by default: API contracts and schema
# migrations, where breaking changes hide without a commit message saying so
DEFAULT_DIFF_PATTERNS = "**/openapi*.yaml,**/migrations/**,**/*.proto"


# Priority patterns for file ordering
PRIORITY_PATTERNS = {
    1: [
        "openapi*.yaml",
        "openapi*.yml",
        "openapi*.json",
        "*.proto",
        "*.graphql",
        "swagger*.yaml",
        "swagger*.yml",
        "swagger*.json",
    ],
    2: [
        "migrations/**",
        "alembic/**",
        "db/migrate/**",
    ],
    3: [
        "*.config.*",
        ".env*",
        "config.*",
        "settings.*",
    ],
}


# MAP prompt for extracting structured changes from a diff
DIFF_MAP_PROMPT = """Analyze this code diff and extract ALL changes.

For each change, classify it as:
- ADDED: new endpoints, functions, fields, classes, features
- REMOVED: deleted endpoints, functions, fields, classes, features
- MODIFIED: changed signatures, schemas, behaviors, configurations

Output in this format:

<CHANGES>
<added>
- Description of added item 1
- Description of added item 2
</added>
<removed>
- Description of removed item 1
</removed>
<modified>
- Description of modified item 1 (what changed)
</modified>
</CHANGES>

If a section has no items, include it empty (e.g., <added></added>).

{notice}

Diff to analyze:
{diff_content}
"""


def parse_patterns(patterns_str: str) -> list[str]:
    """Parse comma-separated patterns string.

    Args:
        patterns_str: Comma-separated gitignore-style patterns.

    Returns:
        List of individual patterns.
    """
    if not patterns_str or not patterns_str.strip():
        return []

    return [p.strip() for p in patterns_str.split(",") if p.strip()]


def parse_unified_diff(diff_text: str) -> list[FileDiff]:
    """Parse unified diff output into FileDiff objects.

    Uses the unidiff library to parse git diff output.

    Args:
        diff_text: Raw git diff output (unified format).

    Returns:
        List of FileDiff objects, one per changed file.
    """
    if not diff_text or not diff_text.strip():
        return []

    try:
        patch_set = PatchSet(diff_text)
    except Exception:
        # If parsing fails, return empty list
        # Caller should handle this case
        return []

    diffs: list[FileDiff] = []

    for patched_file in patch_set:
        # Determine the file path (prefer target path for new/modified files)
        path = patched_file.path
        if path.startswith("b/"):
            path = path[2:]
        elif path.startswith("a/"):
            path = path[2:]

        # Handle /dev/null for new/deleted files
        source_path = patched_file.source_file or ""
        target_path = patched_file.target_file or ""

        if source_path.startswith("a/"):
            source_path = source_path[2:]
        if target_path.startswith("b/"):
            target_path = target_path[2:]

        # Determine if it's a rename
        is_rename = (
            source_path
            and target_path
            and source_path != target_path
            and source_path != "/dev/null"
            and target_path != "/dev/null"
        )

        # Use target path for the final path (or source if target is /dev/null)
        if target_path and target_path != "/dev/null":
            path = target_path
        elif source_path and source_path != "/dev/null":
            path = source_path

        # Extract added and removed lines
        added_lines: list[str] = []
        removed_lines: list[str] = []

        for hunk in patched_file:
            for line in hunk:
                if line.is_added:
                    added_lines.append(line.value.rstrip("\n"))
                elif line.is_removed:
                    removed_lines.append(line.value.rstrip("\n"))

        # Detect binary files (no added/removed lines and special markers)
        is_binary = not added_lines and not removed_lines and len(list(patched_file)) == 0

        file_diff = FileDiff(
            path=path,
            added_lines=added_lines,
            removed_lines=removed_lines,
            is_binary=is_binary,
            is_rename=is_rename,
            old_path=source_path if is_rename else "",
        )

        diffs.append(file_diff)

    return diffs


def select_paths(paths: list[str], patterns: str) -> list[str]:
    """Keep the paths matching comma-separated gitignore-style patterns ("!" negates)."""
    spec = pathspec.PathSpec.from_lines(GitIgnoreSpecPattern, parse_patterns(patterns))
    return [path for path in paths if spec.match_file(path)]


def select_diffs(diffs: list[FileDiff], patterns: str) -> list[FileDiff]:
    """Keep the diffs of files matching gitignore-style patterns.

    Args:
        diffs: List of FileDiff objects to select from.
        patterns: Comma-separated gitignore-style patterns; "!" negates.

    Returns:
        Diffs of matching files.
    """
    selected = set(select_paths([diff.path for diff in diffs], patterns))
    return [diff for diff in diffs if diff.path in selected]


def get_file_priority(path: str) -> int:
    """Determine file priority based on path patterns.

    Priority levels:
    - 1: API specs (openapi, proto, graphql, swagger)
    - 2: Migrations (migrations/**, alembic/**, db/migrate/**)
    - 3: Config files (*.config.*, .env*, config.*, settings.*)
    - 4: Everything else

    Args:
        path: File path to check.

    Returns:
        Priority level (1=highest, 4=lowest).
    """
    for priority, patterns in PRIORITY_PATTERNS.items():
        spec = pathspec.PathSpec.from_lines(GitIgnoreSpecPattern, patterns)
        if spec.match_file(path):
            return priority

    return 4  # Default priority


def prioritize_diffs(diffs: list[FileDiff]) -> list[FileDiff]:
    """Sort diffs by priority (lowest priority number first).

    Args:
        diffs: List of FileDiff objects.

    Returns:
        Sorted list of FileDiff objects.
    """

    def sort_key(diff: FileDiff) -> tuple[int, str]:
        return (get_file_priority(diff.path), diff.path.lower())

    return sorted(diffs, key=sort_key)


def limit_diffs(
    diffs: list[FileDiff],
    max_lines: int,
) -> tuple[list[FileDiff], list[str]]:
    """Apply the line budget to diffs.

    Keeps diffs until the budget is reached, maintaining priority order.

    Args:
        diffs: List of FileDiff objects (should be pre-sorted by priority).
        max_lines: Maximum total lines of changes to include.

    Returns:
        Tuple of (kept_diffs, warnings).
    """
    kept: list[FileDiff] = []
    warnings: list[str] = []
    total_lines = 0

    for diff in diffs:
        if total_lines + diff.line_count > max_lines:
            remaining = len(diffs) - len(kept)
            warnings.append(f"Reached line limit ({max_lines}), skipped {remaining} files")
            break

        kept.append(diff)
        total_lines += diff.line_count

    return kept, warnings


def format_diff_for_prompt(diff: FileDiff) -> str:
    """Format a single FileDiff for LLM analysis.

    Creates a readable representation of the diff for the prompt.

    Args:
        diff: FileDiff object to format.

    Returns:
        Formatted string representation.
    """
    lines = [f"### File: {diff.path}"]

    if diff.is_rename:
        lines.append(f"(Renamed from: {diff.old_path})")

    if diff.is_binary:
        lines.append("(Binary file changed)")
        return "\n".join(lines)

    if diff.removed_lines:
        lines.append("\n--- Removed ---")
        for line in diff.removed_lines[:50]:  # Limit to 50 lines per section
            lines.append(f"- {line}")
        if len(diff.removed_lines) > 50:
            lines.append(f"... and {len(diff.removed_lines) - 50} more lines")

    if diff.added_lines:
        lines.append("\n+++ Added +++")
        for line in diff.added_lines[:50]:  # Limit to 50 lines per section
            lines.append(f"+ {line}")
        if len(diff.added_lines) > 50:
            lines.append(f"... and {len(diff.added_lines) - 50} more lines")

    return "\n".join(lines)


def extract_changes_from_diff(
    diff_content: str,
    llm_caller: Callable[[str], str],
) -> str:
    """Extract structured changes from diff content using LLM.

    This is the MAP phase that extracts ADDED/REMOVED/MODIFIED items.

    Args:
        diff_content: Formatted diff content for a single file or group.
        llm_caller: Function that calls the LLM and returns response.

    Returns:
        Extracted changes in structured format.
    """
    prompt = DIFF_MAP_PROMPT.format(notice=UNTRUSTED_NOTICE, diff_content=wrap(diff_content, "diff"))
    response = llm_caller(prompt)

    # Extract content between <CHANGES> tags
    changes_match = re.search(
        r"<CHANGES>\s*(.*?)\s*</CHANGES>",
        response,
        re.DOTALL | re.IGNORECASE,
    )

    if changes_match:
        return changes_match.group(1).strip()

    # Fallback: return the full response if no tags found
    return response.strip()


def _combine_extracted_changes(changes_list: list[str]) -> str:
    """Combine multiple extracted changes into one summary.

    Merges ADDED/REMOVED/MODIFIED sections from multiple files.

    Args:
        changes_list: List of extracted changes strings.

    Returns:
        Combined changes string.
    """
    added_items: list[str] = []
    removed_items: list[str] = []
    modified_items: list[str] = []

    for changes in changes_list:
        # Extract <added> section
        added_match = re.search(r"<added>\s*(.*?)\s*</added>", changes, re.DOTALL | re.IGNORECASE)
        if added_match:
            items = [
                line.strip().lstrip("-").strip()
                for line in added_match.group(1).strip().split("\n")
                if line.strip() and line.strip() != "-"
            ]
            added_items.extend(items)

        # Extract <removed> section
        removed_match = re.search(r"<removed>\s*(.*?)\s*</removed>", changes, re.DOTALL | re.IGNORECASE)
        if removed_match:
            items = [
                line.strip().lstrip("-").strip()
                for line in removed_match.group(1).strip().split("\n")
                if line.strip() and line.strip() != "-"
            ]
            removed_items.extend(items)

        # Extract <modified> section
        modified_match = re.search(r"<modified>\s*(.*?)\s*</modified>", changes, re.DOTALL | re.IGNORECASE)
        if modified_match:
            items = [
                line.strip().lstrip("-").strip()
                for line in modified_match.group(1).strip().split("\n")
                if line.strip() and line.strip() != "-"
            ]
            modified_items.extend(items)

    # Build combined output
    lines = ["<added>"]
    for item in added_items:
        lines.append(f"- {item}")
    lines.append("</added>")

    lines.append("<removed>")
    for item in removed_items:
        lines.append(f"- {item}")
    lines.append("</removed>")

    lines.append("<modified>")
    for item in modified_items:
        lines.append(f"- {item}")
    lines.append("</modified>")

    return "\n".join(lines)


def analyze_diffs(
    diff_text: str,
    patterns: str,
    max_lines: int,
    llm_caller: Callable[[str], str],
) -> DiffAnalysisResult:
    """Full orchestrator for diff analysis.

    Pipeline:
    1. Parse unified diff
    2. Select files matching the patterns
    3. Prioritize by file type
    4. Apply the line budget
    5. Extract changes via LLM

    Args:
        diff_text: Raw git diff output (unified format).
        patterns: Comma-separated gitignore-style patterns selecting files.
        max_lines: Maximum total lines of changes to process.
        llm_caller: Function that calls the LLM and returns response.

    Returns:
        DiffAnalysisResult with extracted changes and metadata.
    """
    warnings: list[str] = []

    # Step 1: Parse diffs
    diffs = parse_unified_diff(diff_text)
    if not diffs:
        return DiffAnalysisResult(
            extracted_changes="",
            diffs_processed=0,
            total_lines=0,
            warnings=["No valid diffs found in input"],
        )

    # Step 2: Select files matching the patterns
    selected_diffs = select_diffs(diffs, patterns)
    if not selected_diffs:
        # The patterns name specific files: most releases touch none of them
        return DiffAnalysisResult(extracted_changes="", diffs_processed=0, total_lines=0)

    # Step 3: Prioritize
    prioritized_diffs = prioritize_diffs(selected_diffs)

    # Step 4: Apply the line budget
    limited_diffs, limit_warnings = limit_diffs(prioritized_diffs, max_lines)
    warnings.extend(limit_warnings)

    if not limited_diffs:
        return DiffAnalysisResult(
            extracted_changes="",
            diffs_processed=0,
            total_lines=0,
            warnings=warnings + ["No files remaining after applying limits"],
        )

    # Step 5: Format and extract changes
    # Group diffs into batches to avoid overly long prompts
    batch_size = 5  # Process 5 files at a time
    all_changes: list[str] = []
    total_lines = 0

    for i in range(0, len(limited_diffs), batch_size):
        batch = limited_diffs[i : i + batch_size]

        # Format batch for prompt
        batch_content = "\n\n".join(format_diff_for_prompt(d) for d in batch)

        # Check if batch is too large
        batch_tokens = estimate_tokens(batch_content)
        if batch_tokens > 4000:
            # Process individually if batch is too large
            for diff in batch:
                diff_content = format_diff_for_prompt(diff)
                changes = extract_changes_from_diff(diff_content, llm_caller)
                if changes:
                    all_changes.append(changes)
                total_lines += diff.line_count
        else:
            # Process batch together
            changes = extract_changes_from_diff(batch_content, llm_caller)
            if changes:
                all_changes.append(changes)
            total_lines += sum(d.line_count for d in batch)

    # Combine all extracted changes
    combined_changes = _combine_extracted_changes(all_changes) if all_changes else ""

    return DiffAnalysisResult(
        extracted_changes=combined_changes,
        diffs_processed=len(limited_diffs),
        total_lines=total_lines,
        warnings=warnings,
    )
