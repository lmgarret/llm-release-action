"""Workload Identity Federation for the Anthropic API.

Lets the action call Claude without a static ANTHROPIC_API_KEY: a JWT from an
OIDC identity provider (typically the GitHub Actions OIDC token) is exchanged
at POST /v1/oauth/token for a short-lived access token, which is sent as
``Authorization: Bearer`` on every Anthropic request.

Configuration uses the same environment variables as the official Anthropic
SDKs:

    ANTHROPIC_FEDERATION_RULE_ID   (required) fdrl_...
    ANTHROPIC_ORGANIZATION_ID      (required) organization UUID
    ANTHROPIC_SERVICE_ACCOUNT_ID   (optional) svac_...
    ANTHROPIC_WORKSPACE_ID         (optional) wrkspc_..., needed when the rule
                                   spans multiple workspaces
    ANTHROPIC_IDENTITY_TOKEN_FILE  (optional) path to the JWT, re-read on
                                   every exchange
    ANTHROPIC_IDENTITY_TOKEN       (optional) the JWT itself

When neither identity token variable is set and the job runs on GitHub Actions
with ``id-token: write``, a fresh OIDC token is requested for every exchange
(GitHub tokens expire after ~5 minutes and are single-use for the exchange).
Its audience defaults to https://api.anthropic.com and can be overridden with
ANTHROPIC_IDENTITY_TOKEN_AUDIENCE.

LiteLLM always authenticates Anthropic with ``x-api-key``, so federation is
wired in through a custom HTTP client whose request hook swaps that header for
the Bearer token.
"""

import os
import threading
import time
from typing import Optional
from urllib.parse import urlparse

import httpx

TOKEN_ENDPOINT = "/v1/oauth/token"
GRANT_TYPE_JWT_BEARER = "urn:ietf:params:oauth:grant-type:jwt-bearer"
# oauth-2025-04-20 unlocks Bearer auth; oidc-federation-2026-04-01 routes the
# jwt-bearer exchange to the federation handler.
OAUTH_BETA = "oauth-2025-04-20"
FEDERATION_BETA = "oidc-federation-2026-04-01"
DEFAULT_BASE_URL = "https://api.anthropic.com"
DEFAULT_AUDIENCE = "https://api.anthropic.com"
# Refresh this many seconds before the access token expires.
REFRESH_MARGIN_SECONDS = 120
EXCHANGE_TIMEOUT_SECONDS = 30.0

# LiteLLM refuses to call Anthropic without an api_key; this value is never
# sent because the request hook strips x-api-key.
PLACEHOLDER_API_KEY = "federated"


class FederationError(RuntimeError):
    """Raised when the identity token cannot be obtained or exchanged."""


def federation_configured() -> bool:
    """True if federation env vars are set and no API key takes precedence.

    Mirrors the SDK precedence: ANTHROPIC_API_KEY / ANTHROPIC_AUTH_TOKEN win
    over federation.
    """
    if os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"):
        return False
    return bool(
        os.environ.get("ANTHROPIC_FEDERATION_RULE_ID")
        and os.environ.get("ANTHROPIC_ORGANIZATION_ID")
    )


def _base_url() -> str:
    return (
        os.environ.get("ANTHROPIC_API_BASE")
        or os.environ.get("ANTHROPIC_BASE_URL")
        or DEFAULT_BASE_URL
    ).rstrip("/")


def _fetch_github_oidc_token(audience: str) -> str:
    """Request a fresh OIDC token from the GitHub Actions runner."""
    request_url = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
    request_token = os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    if not request_url or not request_token:
        raise FederationError(
            "No identity token available: set ANTHROPIC_IDENTITY_TOKEN_FILE or "
            "ANTHROPIC_IDENTITY_TOKEN, or run on GitHub Actions with "
            "`permissions: id-token: write`."
        )
    resp = httpx.get(
        request_url,
        params={"audience": audience},
        headers={"Authorization": f"Bearer {request_token}"},
        timeout=EXCHANGE_TIMEOUT_SECONDS,
    )
    if resp.status_code >= 400:
        raise FederationError(
            f"GitHub OIDC token request failed with status {resp.status_code}"
        )
    token = resp.json().get("value")
    if not token:
        raise FederationError("GitHub OIDC token response missing 'value'")
    return token


def read_identity_token() -> str:
    """Return a JWT to exchange: explicit file/value, else GitHub OIDC."""
    path = os.environ.get("ANTHROPIC_IDENTITY_TOKEN_FILE")
    if path:
        try:
            with open(path, encoding="utf-8") as f:
                token = f.read().strip()
        except OSError as e:
            raise FederationError(f"Cannot read ANTHROPIC_IDENTITY_TOKEN_FILE: {e}") from e
        if not token:
            raise FederationError(f"ANTHROPIC_IDENTITY_TOKEN_FILE {path} is empty")
        return token

    token = os.environ.get("ANTHROPIC_IDENTITY_TOKEN", "").strip()
    if token:
        return token

    audience = os.environ.get("ANTHROPIC_IDENTITY_TOKEN_AUDIENCE") or DEFAULT_AUDIENCE
    return _fetch_github_oidc_token(audience)


class FederatedTokenProvider:
    """Exchanges identity tokens for Anthropic access tokens and caches them.

    Thread-safe: analysis runs LLM calls from a thread pool.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or _base_url()).rstrip("/")
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._expires_at = 0.0

    def get_token(self) -> str:
        with self._lock:
            if self._token is None or time.time() >= self._expires_at - REFRESH_MARGIN_SECONDS:
                self._token, self._expires_at = self._exchange()
            return self._token

    def _exchange(self):
        body = {
            "grant_type": GRANT_TYPE_JWT_BEARER,
            "assertion": read_identity_token(),
            "federation_rule_id": os.environ["ANTHROPIC_FEDERATION_RULE_ID"],
            "organization_id": os.environ["ANTHROPIC_ORGANIZATION_ID"],
        }
        for key, env in (
            ("service_account_id", "ANTHROPIC_SERVICE_ACCOUNT_ID"),
            ("workspace_id", "ANTHROPIC_WORKSPACE_ID"),
        ):
            if os.environ.get(env):
                body[key] = os.environ[env]

        try:
            resp = httpx.post(
                f"{self.base_url}{TOKEN_ENDPOINT}",
                json=body,
                headers={"anthropic-beta": f"{OAUTH_BETA},{FEDERATION_BETA}"},
                timeout=EXCHANGE_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as e:
            raise FederationError(f"Failed to reach Anthropic token endpoint: {e}") from e

        if resp.status_code >= 400:
            # The body can echo the assertion; report only the status.
            hint = ""
            if resp.status_code == 401:
                hint = (
                    " Check that the federation rule matches the identity token "
                    "(see the Workload identity authentication history in the "
                    "Claude Console); set ANTHROPIC_WORKSPACE_ID if the rule "
                    "spans multiple workspaces."
                )
            raise FederationError(
                f"Anthropic token exchange failed with status {resp.status_code}.{hint}"
            )

        data = resp.json()
        try:
            token = data["access_token"]
            expires_in = int(data["expires_in"])
        except (KeyError, TypeError, ValueError) as e:
            raise FederationError(
                "Anthropic token exchange response missing access_token/expires_in"
            ) from e
        return token, time.time() + expires_in


def _merge_beta(existing: Optional[str], beta: str) -> str:
    betas = [b.strip() for b in (existing or "").split(",") if b.strip()]
    if beta not in betas:
        betas.append(beta)
    return ",".join(betas)


def build_http_client(
    provider: FederatedTokenProvider,
    transport: Optional[httpx.BaseTransport] = None,
):
    """Return a LiteLLM HTTPHandler that authenticates with federated tokens."""
    from litellm.llms.custom_httpx.http_handler import HTTPHandler

    api_host = urlparse(provider.base_url).netloc

    def _authenticate(request: httpx.Request) -> None:
        if request.url.netloc.decode() != api_host:
            return
        request.headers.pop("x-api-key", None)
        request.headers["authorization"] = f"Bearer {provider.get_token()}"
        request.headers["anthropic-beta"] = _merge_beta(
            request.headers.get("anthropic-beta"), OAUTH_BETA
        )

    return HTTPHandler(
        client=httpx.Client(
            event_hooks={"request": [_authenticate]},
            follow_redirects=True,
            transport=transport,
        )
    )


_client = None
_client_lock = threading.Lock()


def get_federated_client():
    """Process-wide federated HTTP client, created on first use."""
    global _client
    with _client_lock:
        if _client is None:
            _client = build_http_client(FederatedTokenProvider())
        return _client
