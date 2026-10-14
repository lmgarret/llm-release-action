"""Semantic version parsing and manipulation utilities."""

import re
import subprocess
from dataclasses import dataclass

SEMVER_TAG_PATTERN = re.compile(r"^v?\d+\.\d+\.\d+(-[\w.]+)?$")


@dataclass
class SemanticVersion:
    """Represents a semantic version."""

    major: int
    minor: int
    patch: int
    prerelease: str | None = None

    def __str__(self) -> str:
        """Return version string with v prefix."""
        base = f"v{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            return f"{base}-{self.prerelease}"
        return base

    def bump(self, bump_type: str) -> "SemanticVersion":
        """Return a new version with the specified bump applied."""
        if bump_type == "major":
            return SemanticVersion(self.major + 1, 0, 0)
        elif bump_type == "minor":
            return SemanticVersion(self.major, self.minor + 1, 0)
        elif bump_type == "patch":
            if self.prerelease:
                # Bump prerelease suffix
                return self._bump_prerelease()
            return SemanticVersion(self.major, self.minor, self.patch + 1)
        else:
            raise ValueError(f"Invalid bump type: {bump_type}. Must be major, minor, or patch.")

    def _bump_prerelease(self) -> "SemanticVersion":
        """Bump the prerelease version suffix."""
        if not self.prerelease:
            raise ValueError("Cannot bump prerelease on a non-prerelease version")

        # Match pattern like alpha.1, beta.2, rc.3
        match = re.match(r"^(.+)\.(\d+)$", self.prerelease)
        if match:
            prefix = match.group(1)
            number = int(match.group(2))
            new_prerelease = f"{prefix}.{number + 1}"
            return SemanticVersion(self.major, self.minor, self.patch, new_prerelease)

        # No numeric suffix, append .1
        return SemanticVersion(self.major, self.minor, self.patch, f"{self.prerelease}.1")


def parse_version(version_str: str) -> SemanticVersion:
    """Parse a version string into a SemanticVersion object.

    Args:
        version_str: Version string like "v1.2.3" or "1.2.3-alpha.1"

    Returns:
        SemanticVersion object

    Raises:
        ValueError: If the version string is invalid
    """
    # Remove v prefix if present
    version_str = version_str.lstrip("v")

    # Split prerelease suffix
    prerelease = None
    if "-" in version_str:
        version_str, prerelease = version_str.split("-", 1)

    # Parse major.minor.patch
    parts = version_str.split(".")
    if len(parts) != 3:
        raise ValueError(f"Invalid version format: {version_str}. Expected major.minor.patch")

    try:
        major = int(parts[0])
        minor = int(parts[1])
        patch = int(parts[2])
    except ValueError as e:
        raise ValueError(f"Invalid version numbers in {version_str}: {e}") from e

    if major < 0 or minor < 0 or patch < 0:
        raise ValueError(f"Version numbers cannot be negative: {version_str}")

    return SemanticVersion(major, minor, patch, prerelease)


def detect_latest_tag() -> str | None:
    """Detect the latest semver tag from git.

    Returns:
        The latest semver tag (e.g., "v1.2.3") or None if no tags found
    """
    try:
        result = subprocess.run(
            ["git", "tag", "--list", "v*", "--sort=-v:refname"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Failed to list git tags: {e.stderr}") from e

    tags = result.stdout.strip().split("\n")
    tags = [t for t in tags if t]  # Remove empty strings

    # Find first valid semver tag
    for tag in tags:
        if SEMVER_TAG_PATTERN.match(tag):
            return tag

    return None


def _describe(ref: str, match: str) -> str | None:
    """Nearest tag matching `match` reachable from `ref`, or None."""
    result = subprocess.run(
        ["git", "describe", "--tags", "--abbrev=0", "--match", match, ref],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def detect_previous_tag(pattern: str, head_ref: str) -> str | None:
    """Nearest tag matching `pattern` strictly before `head_ref`.

    Tags on `head_ref` itself are skipped, so when the release being described
    is already tagged (e.g. a workflow triggered by pushing that tag), the
    previous release is returned rather than the current one.
    """
    return _describe(f"{head_ref}^", pattern)


def detect_semver_tag_at_or_before(ref: str) -> str | None:
    """Nearest semver tag reachable from `ref` (including `ref` itself), or None."""
    tag = _describe(ref, "v*")
    return tag if tag and SEMVER_TAG_PATTERN.match(tag) else None


def tags_pointing_at(ref: str, pattern: str) -> list[str]:
    """Tags matching `pattern` that point at `ref`."""
    result = subprocess.run(
        ["git", "tag", "--points-at", ref, "--list", pattern],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    return result.stdout.split()


def is_shallow_clone() -> bool:
    """Check if the repository is a shallow clone."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-shallow-repository"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip() == "true"
    except subprocess.CalledProcessError:
        return False


VERSIONING_SCHEMES = ("semver", "none")
UNRELEASED_LABEL = "Unreleased"


@dataclass
class ReleaseRange:
    """Where the analyzed commit range starts, and the version it starts from.

    `version` is None when versioning is "none": the range is then only a pair
    of git refs and no next version is computed.
    """

    base_ref: str
    version: SemanticVersion | None


def _is_tag(ref: str) -> bool:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{ref}"],
        capture_output=True,
    )
    return result.returncode == 0


def _detect_base_ref(versioning: str, tag_pattern: str, head_ref: str) -> str:
    """Previous release tag, found by `tag_pattern` or (for semver) the latest v* tag."""
    if tag_pattern or versioning == "none":
        pattern = tag_pattern or "*"
        tag = detect_previous_tag(pattern, head_ref)
        if not tag:
            raise ValueError(f"No tag matching '{pattern}' found before {head_ref}. Set base_ref.")
        return tag
    tag = detect_latest_tag()
    if not tag:
        raise ValueError("No semver tags found. Set current_version or base_ref.")
    return tag


def _semver_base(base_ref: str, current_version: str) -> SemanticVersion:
    """The version to bump from: current_version, else the base ref or the nearest v* tag before it."""
    if current_version:
        return parse_version(current_version)
    if SEMVER_TAG_PATTERN.match(base_ref):
        return parse_version(base_ref)
    tag = detect_semver_tag_at_or_before(base_ref)
    if not tag:
        raise ValueError(
            f"'{base_ref}' is not a semver version and no semver tag precedes it. "
            "Set current_version, or versioning: none to skip version calculation."
        )
    return parse_version(tag)


def resolve_release_range(
    versioning: str,
    head_ref: str,
    base_ref: str = "",
    current_version: str = "",
    tag_pattern: str = "",
) -> ReleaseRange:
    """Resolve the commit range and base version from the action inputs.

    The range starts at base_ref, else current_version (which has always
    doubled as a ref), else the previous release tag.

    Raises:
        ValueError: If no base can be found, or semver needs a version that cannot be derived
    """
    base = base_ref or current_version or _detect_base_ref(versioning, tag_pattern, head_ref)
    if versioning == "none":
        return ReleaseRange(base_ref=base, version=None)
    return ReleaseRange(base_ref=base, version=_semver_base(base, current_version))


def resolve_release_label(head_ref: str, tag_pattern: str = "", release_name: str = "") -> str:
    """Name of the release being described, for changelogs when there is no next version.

    release_name if set, else head_ref when it is a tag, else a tag matching
    tag_pattern on head_ref (a tag-triggered run checking out HEAD), else "Unreleased".
    """
    if release_name:
        return release_name
    if head_ref != "HEAD" and _is_tag(head_ref):
        return head_ref
    tags = tags_pointing_at(head_ref, tag_pattern or "*")
    return tags[0] if tags else UNRELEASED_LABEL
