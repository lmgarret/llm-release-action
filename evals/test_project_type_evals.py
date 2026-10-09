"""End-to-end evaluations for project type detection and type-specific breaking rules.

Run with: PYTHONPATH=src pytest evals/test_project_type_evals.py -v -m eval

Requires AWS credentials configured for Bedrock access.
"""

import litellm
import pytest

from analyzer import parse_phase1_response
from conftest import completion_kwargs, get_test_model
from project_profile import ProjectProfile, build_profile_prompt, parse_profile_response
from prompt_builder import CommitInfo, build_semantic_analysis_prompt

pytestmark = [
    pytest.mark.eval,
    pytest.mark.slow,
]


def call_llm(prompt: str, max_tokens: int = 2000) -> str:
    """Call LLM via LiteLLM."""
    response = litellm.completion(
        messages=[{"role": "user", "content": prompt}],
        **completion_kwargs(get_test_model(), temperature=0.0, max_tokens=max_tokens),
    )
    return response.choices[0].message.content


# =============================================================================
# Detection
# =============================================================================

DETECTION_CASES = [
    (
        "app",
        "# Pocket Notes\n\nA private, offline note-taking app for Android. Available on F-Droid and Google Play.",
        ["README.md", "app/build.gradle.kts", "app/src/", "build.gradle.kts", "fastlane/metadata/", "gradle/", "gradlew", "settings.gradle.kts"],
    ),
    (
        "library",
        "# tinydate\n\nA tiny date formatting library.\n\n```js\nimport { format } from 'tinydate'\n```",
        ["README.md", "package.json", "src/format.ts", "src/index.ts", "test/format.test.ts", "tsconfig.json"],
    ),
    (
        "api",
        "# Acme Payments API\n\nPublic REST API for merchants. See the OpenAPI spec for endpoints and authentication.",
        ["Dockerfile", "README.md", "api/openapi.yaml", "cmd/server/", "go.mod", "internal/handlers/"],
    ),
    (
        "service",
        "# Hoard\n\nSelf-hosted media server. Run it with Docker Compose and configure it via environment variables.",
        ["Dockerfile", "README.md", "charts/hoard/", "docker-compose.yml", "migrations/", "src/"],
    ),
]


class TestDetection:
    @pytest.mark.parametrize("expected,readme,tree", DETECTION_CASES, ids=[c[0] for c in DETECTION_CASES])
    def test_detects_type(self, expected: str, readme: str, tree: list) -> None:
        response = call_llm(build_profile_prompt(readme, tree), max_tokens=300)
        profile = parse_profile_response(response)
        assert profile.project_type == expected, f"Expected {expected}, got {profile.project_type}: {response}"


# =============================================================================
# Type-specific breaking rules
# =============================================================================

APP_MIGRATION_COMMITS = [
    CommitInfo(hash="a1b2c3d", message="feat: add tags to notes"),
    CommitInfo(
        hash="b2c3d4e",
        message="refactor(db): migrate local Room database to v12 schema\n\n"
        "Drops the legacy notes_old table and renames columns. Downgrading is no longer possible.",
    ),
    CommitInfo(hash="c3d4e5f", message="fix: crash when sharing an empty note"),
]

LIBRARY_REMOVAL_COMMITS = [
    CommitInfo(hash="d4e5f6a", message="refactor: remove deprecated formatLegacy() export"),
    CommitInfo(hash="e5f6a7b", message="fix: handle leap years in format()"),
]


class TestBreakingRules:
    def analyze(self, commits, profile: ProjectProfile) -> str:
        prompt = build_semantic_analysis_prompt(
            commits=commits,
            base_version="v2.3.0",
            project_profile=profile,
        )
        return parse_phase1_response(call_llm(prompt)).bump

    def test_app_internal_migration_not_major(self) -> None:
        bump = self.analyze(APP_MIGRATION_COMMITS, ProjectProfile(project_type="app", consumers="Android users"))
        assert bump == "minor", f"Internal app DB migration should not be major, got {bump}"

    def test_library_removed_export_is_major(self) -> None:
        bump = self.analyze(LIBRARY_REMOVAL_COMMITS, ProjectProfile(project_type="library"))
        assert bump == "major", f"Removing a public export should be major, got {bump}"
