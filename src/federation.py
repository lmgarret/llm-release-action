"""Anthropic Workload Identity Federation: authenticate without an API key.

When ANTHROPIC_FEDERATION_RULE_ID is set, an OIDC token (from GitHub Actions,
or from ANTHROPIC_IDENTITY_TOKEN_FILE / ANTHROPIC_IDENTITY_TOKEN) is exchanged
for a short-lived Anthropic access token. LiteLLM reads that token from
ANTHROPIC_AUTH_TOKEN and sends it as a bearer token. The token is set in this
process only, so later workflow steps never see it.

The environment variables are the ones the Anthropic SDKs read:
https://platform.claude.com/docs/en/manage-claude/wif-reference#environment-variables
"""

import json
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass

REQUIRED_VARS = ("ANTHROPIC_FEDERATION_RULE_ID", "ANTHROPIC_ORGANIZATION_ID", "ANTHROPIC_SERVICE_ACCOUNT_ID")
# Credentials LiteLLM prefers over ANTHROPIC_AUTH_TOKEN, so they would silently shadow federation
SHADOWING_VARS = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN")
GITHUB_AUDIENCE = "https://api.anthropic.com"
DEFAULT_BASE_URL = "https://api.anthropic.com"
JWT_BEARER_GRANT = "urn:ietf:params:oauth:grant-type:jwt-bearer"
# Re-exchange this long before expiry. Tokens can last as little as 60 seconds,
# so never less than half their lifetime either.
REFRESH_MARGIN_SECONDS = 120
HTTP_TIMEOUT_SECONDS = 30


class FederationError(RuntimeError):
    """Federation is misconfigured or the token exchange failed."""


def _request_json(url: str, body: dict[str, str] | None, headers: dict[str, str]) -> dict:
    """POST (or GET, without a body) and decode a JSON response.

    Raises:
        FederationError: On an HTTP or network error, with the response's error message
    """
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method="POST" if data else "GET")
    try:
        with urllib.request.urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed https URLs
            return json.loads(response.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise FederationError(f"{url.split('?')[0]} returned HTTP {e.code}: {detail}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise FederationError(f"Could not reach {url.split('?')[0]}: {e}") from e


def github_identity_token(env: Mapping[str, str]) -> str:
    """Request a fresh OIDC token from GitHub Actions, with the Anthropic API as audience.

    A new token each time: Anthropic rejects a token whose jti it has already seen.
    """
    url = env.get("ACTIONS_ID_TOKEN_REQUEST_URL")
    request_token = env.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not url or not request_token:
        raise FederationError(
            "No identity token: give the job `permissions: id-token: write`, "
            "or set ANTHROPIC_IDENTITY_TOKEN_FILE or ANTHROPIC_IDENTITY_TOKEN"
        )
    separator = "&" if "?" in url else "?"
    full_url = f"{url}{separator}audience={urllib.parse.quote(GITHUB_AUDIENCE, safe='')}"
    response = _request_json(full_url, None, {"Authorization": f"Bearer {request_token}"})
    token = response.get("value")
    if not token:
        raise FederationError("GitHub returned no OIDC token")
    return token


def identity_token_source(env: Mapping[str, str]) -> Callable[[], str]:
    """Where each exchange gets its OIDC token: a file (re-read every time), a literal, or GitHub."""
    token_file = env.get("ANTHROPIC_IDENTITY_TOKEN_FILE")
    if token_file:

        def read_file() -> str:
            try:
                with open(token_file, encoding="utf-8") as f:
                    return f.read().strip()
            except OSError as e:
                raise FederationError(f"Cannot read ANTHROPIC_IDENTITY_TOKEN_FILE: {e}") from e

        return read_file
    literal = env.get("ANTHROPIC_IDENTITY_TOKEN")
    if literal:
        return lambda: literal
    return lambda: github_identity_token(env)


@dataclass
class FederationConfig:
    """What the token exchange sends, read from the environment."""

    rule_id: str
    organization_id: str
    service_account_id: str
    workspace_id: str | None
    base_url: str
    identity_token: Callable[[], str]

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "FederationConfig | None":
        """The federation settings, or None when ANTHROPIC_FEDERATION_RULE_ID is unset.

        Raises:
            FederationError: If a required variable is missing, or a key would shadow federation
        """
        if not env.get("ANTHROPIC_FEDERATION_RULE_ID"):
            return None
        missing = [name for name in REQUIRED_VARS if not env.get(name)]
        if missing:
            raise FederationError(f"Workload Identity Federation needs {', '.join(missing)}")
        shadowing = [name for name in SHADOWING_VARS if env.get(name)]
        if shadowing:
            raise FederationError(
                f"{', '.join(shadowing)} is set alongside ANTHROPIC_FEDERATION_RULE_ID; "
                "remove it to use Workload Identity Federation"
            )
        return cls(
            rule_id=env["ANTHROPIC_FEDERATION_RULE_ID"],
            organization_id=env["ANTHROPIC_ORGANIZATION_ID"],
            service_account_id=env["ANTHROPIC_SERVICE_ACCOUNT_ID"],
            workspace_id=env.get("ANTHROPIC_WORKSPACE_ID") or None,
            base_url=(env.get("ANTHROPIC_BASE_URL") or DEFAULT_BASE_URL).rstrip("/"),
            identity_token=identity_token_source(env),
        )


class FederatedToken:
    """A cached Anthropic access token, re-exchanged before it expires."""

    def __init__(self, config: FederationConfig, clock: Callable[[], float] = time.time):
        self.config = config
        self.clock = clock
        self.token: str | None = None
        self.refresh_at = 0.0
        self.lock = threading.Lock()

    def exchange(self) -> tuple[str, int]:
        """Trade an OIDC token for an Anthropic access token and its lifetime in seconds."""
        body = {
            "grant_type": JWT_BEARER_GRANT,
            "assertion": self.config.identity_token(),
            "federation_rule_id": self.config.rule_id,
            "organization_id": self.config.organization_id,
            "service_account_id": self.config.service_account_id,
        }
        if self.config.workspace_id:
            body["workspace_id"] = self.config.workspace_id
        response = _request_json(f"{self.config.base_url}/v1/oauth/token", body, {"content-type": "application/json"})
        token = response.get("access_token")
        if not token:
            raise FederationError("Token exchange returned no access_token")
        return token, int(response.get("expires_in", 60))

    def get(self) -> str:
        """The current token, exchanging a new one when it is missing or close to expiry."""
        with self.lock:
            now = self.clock()
            if self.token is None or now >= self.refresh_at:
                token, lifetime = self.exchange()
                # Never printed, but masked in case a debug log echoes a header.
                # Only on Actions: elsewhere this line would print the token.
                if os.environ.get("GITHUB_ACTIONS") == "true":
                    print(f"::add-mask::{token}")
                self.token = token
                self.refresh_at = now + lifetime - min(REFRESH_MARGIN_SECONDS, lifetime / 2)
            return self.token


_token: FederatedToken | None = None
_loaded = False
_load_lock = threading.Lock()


def refresh_auth_token() -> bool:
    """Put a valid federated token in ANTHROPIC_AUTH_TOKEN, when federation is configured.

    Called before every LLM call; a no-op without ANTHROPIC_FEDERATION_RULE_ID.

    Returns:
        Whether federation is in use

    Raises:
        FederationError: If federation is misconfigured or the exchange fails
    """
    global _token, _loaded
    with _load_lock:
        if not _loaded:
            config = FederationConfig.from_env(os.environ)
            _token = FederatedToken(config) if config else None
            _loaded = True
    if _token is None:
        return False
    # Blank (an unset GitHub secret) still counts as a key to LiteLLM and blocks the bearer token
    if os.environ.get("ANTHROPIC_API_KEY") == "":
        del os.environ["ANTHROPIC_API_KEY"]
    os.environ["ANTHROPIC_AUTH_TOKEN"] = _token.get()
    return True
