"""Tests for Anthropic Workload Identity Federation support."""

import json
import os
import sys

import httpx
import litellm
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import anthropic_federation as fed  # noqa: E402
from analyze import build_completion_kwargs  # noqa: E402

FED_ENV = {
    "ANTHROPIC_FEDERATION_RULE_ID": "fdrl_test",
    "ANTHROPIC_ORGANIZATION_ID": "00000000-0000-0000-0000-000000000000",
    "ANTHROPIC_SERVICE_ACCOUNT_ID": "svac_test",
}


@pytest.fixture
def fed_env(monkeypatch):
    for var in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_WORKSPACE_ID",
        "ANTHROPIC_IDENTITY_TOKEN",
        "ANTHROPIC_IDENTITY_TOKEN_FILE",
        "ANTHROPIC_IDENTITY_TOKEN_AUDIENCE",
        "ANTHROPIC_API_BASE",
        "ANTHROPIC_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)
    for key, value in FED_ENV.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(fed, "_client", None)


class _Resp:
    def __init__(self, status_code, payload):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class TestFederationConfigured:
    def test_enabled_with_rule_and_org(self, fed_env):
        assert fed.federation_configured()

    def test_api_key_takes_precedence(self, fed_env, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        assert not fed.federation_configured()

    def test_disabled_without_org(self, fed_env, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_ORGANIZATION_ID")
        assert not fed.federation_configured()


class TestIdentityToken:
    def test_reads_token_file(self, fed_env, monkeypatch, tmp_path):
        path = tmp_path / "jwt"
        path.write_text("jwt-from-file\n")
        monkeypatch.setenv("ANTHROPIC_IDENTITY_TOKEN_FILE", str(path))
        assert fed.read_identity_token() == "jwt-from-file"

    def test_reads_token_env(self, fed_env, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_IDENTITY_TOKEN", "jwt-from-env")
        assert fed.read_identity_token() == "jwt-from-env"

    def test_fetches_github_oidc_token(self, fed_env, monkeypatch):
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_URL", "https://gh.example/token?x=1")
        monkeypatch.setenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", "req-token")
        calls = []

        def fake_get(url, params, headers, timeout):
            calls.append((url, params, headers))
            return _Resp(200, {"value": "gh-jwt"})

        monkeypatch.setattr(fed.httpx, "get", fake_get)
        assert fed.read_identity_token() == "gh-jwt"
        assert calls[0][1] == {"audience": "https://api.anthropic.com"}
        assert calls[0][2] == {"Authorization": "Bearer req-token"}

    def test_no_source_raises(self, fed_env, monkeypatch):
        monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_URL", raising=False)
        monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
        with pytest.raises(fed.FederationError, match="id-token: write"):
            fed.read_identity_token()


class TestTokenProvider:
    def test_exchange_and_cache(self, fed_env, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_IDENTITY_TOKEN", "jwt")
        monkeypatch.setenv("ANTHROPIC_WORKSPACE_ID", "wrkspc_test")
        posts = []

        def fake_post(url, json, headers, timeout):
            posts.append((url, json, headers))
            return _Resp(200, {"access_token": "sk-ant-oat01-x", "expires_in": 600})

        monkeypatch.setattr(fed.httpx, "post", fake_post)
        provider = fed.FederatedTokenProvider()
        assert provider.get_token() == "sk-ant-oat01-x"
        assert provider.get_token() == "sk-ant-oat01-x"
        assert len(posts) == 1

        url, body, headers = posts[0]
        assert url == "https://api.anthropic.com/v1/oauth/token"
        assert body == {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": "jwt",
            "federation_rule_id": "fdrl_test",
            "organization_id": "00000000-0000-0000-0000-000000000000",
            "service_account_id": "svac_test",
            "workspace_id": "wrkspc_test",
        }
        assert headers["anthropic-beta"] == "oauth-2025-04-20,oidc-federation-2026-04-01"

    def test_refreshes_near_expiry(self, fed_env, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_IDENTITY_TOKEN", "jwt")
        tokens = iter(["first", "second"])
        monkeypatch.setattr(
            fed.httpx,
            "post",
            lambda *a, **k: _Resp(200, {"access_token": next(tokens), "expires_in": 60}),
        )
        provider = fed.FederatedTokenProvider()
        assert provider.get_token() == "first"
        # 60s lifetime is inside the refresh margin, so the next call re-exchanges.
        assert provider.get_token() == "second"

    def test_exchange_failure_does_not_leak_body(self, fed_env, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_IDENTITY_TOKEN", "secret-jwt")
        monkeypatch.setattr(
            fed.httpx, "post", lambda *a, **k: _Resp(401, {"echo": "secret-jwt"})
        )
        with pytest.raises(fed.FederationError) as exc:
            fed.FederatedTokenProvider().get_token()
        assert "401" in str(exc.value)
        assert "secret-jwt" not in str(exc.value)


class TestCompletionKwargs:
    def test_anthropic_model_uses_federated_client(self, fed_env):
        kwargs = build_completion_kwargs(
            model="anthropic/claude-sonnet-4-5",
            prompt="hi",
            temperature=None,
            max_tokens=100,
            timeout=30,
        )
        assert kwargs["api_key"] == fed.PLACEHOLDER_API_KEY
        assert kwargs["client"] is fed.get_federated_client()

    def test_other_providers_untouched(self, fed_env):
        kwargs = build_completion_kwargs(
            model="bedrock/us.anthropic.claude-haiku-4-5-20251001-v1:0",
            prompt="hi",
            temperature=None,
            max_tokens=100,
            timeout=30,
        )
        assert "client" not in kwargs
        assert "api_key" not in kwargs

    def test_api_key_disables_federation(self, fed_env, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        kwargs = build_completion_kwargs(
            model="anthropic/claude-sonnet-4-5",
            prompt="hi",
            temperature=None,
            max_tokens=100,
            timeout=30,
        )
        assert "client" not in kwargs


def test_litellm_request_uses_bearer_token(fed_env, monkeypatch):
    """End to end through LiteLLM: x-api-key is replaced by the Bearer token."""
    monkeypatch.setattr(
        fed.httpx,
        "post",
        lambda *a, **k: _Resp(200, {"access_token": "sk-ant-oat01-abc", "expires_in": 600}),
    )
    monkeypatch.setenv("ANTHROPIC_IDENTITY_TOKEN", "jwt")
    # Avoid tiktoken downloading its encoding; usage comes from the response.
    monkeypatch.setattr(litellm.main, "_get_encoding", lambda: None)
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "id": "msg_1",
                "type": "message",
                "role": "assistant",
                "model": "claude-sonnet-4-5",
                "content": [{"type": "text", "text": "hello"}],
                "stop_reason": "end_turn",
                "stop_sequence": None,
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    client = fed.build_http_client(
        fed.FederatedTokenProvider(), transport=httpx.MockTransport(handler)
    )
    response = litellm.completion(
        model="anthropic/claude-sonnet-4-5",
        messages=[{"role": "user", "content": "hi"}],
        max_tokens=10,
        api_key=fed.PLACEHOLDER_API_KEY,
        client=client,
    )

    assert response.choices[0].message.content == "hello"
    headers = seen["headers"]
    assert "x-api-key" not in headers
    assert headers["authorization"] == "Bearer sk-ant-oat01-abc"
    assert "oauth-2025-04-20" in headers["anthropic-beta"].split(",")
    assert json.dumps(headers).find(fed.PLACEHOLDER_API_KEY) == -1
