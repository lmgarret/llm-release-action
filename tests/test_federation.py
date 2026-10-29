"""Tests for Anthropic Workload Identity Federation."""

import os
import sys
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import federation
from federation import (
    FederatedToken,
    FederationConfig,
    FederationError,
    github_identity_token,
    identity_token_source,
)

BASE_ENV = {
    "ANTHROPIC_FEDERATION_RULE_ID": "fdrl_1",
    "ANTHROPIC_ORGANIZATION_ID": "org-uuid",
    "ANTHROPIC_SERVICE_ACCOUNT_ID": "svac_1",
    "ANTHROPIC_IDENTITY_TOKEN": "jwt",
}


def make_config(**overrides) -> FederationConfig:
    values = {
        "rule_id": "fdrl_1",
        "organization_id": "org-uuid",
        "service_account_id": "svac_1",
        "workspace_id": None,
        "base_url": "https://api.anthropic.com",
        "identity_token": lambda: "jwt",
    }
    values.update(overrides)
    return FederationConfig(**values)


class TestFromEnv:
    def test_unset_rule_disables_federation(self):
        assert FederationConfig.from_env({"ANTHROPIC_API_KEY": "sk-ant-x"}) is None

    def test_reads_all_fields(self):
        env = {**BASE_ENV, "ANTHROPIC_WORKSPACE_ID": "wrkspc_1", "ANTHROPIC_BASE_URL": "https://proxy.example.com/"}
        config = FederationConfig.from_env(env)
        assert config is not None
        assert config.rule_id == "fdrl_1"
        assert config.workspace_id == "wrkspc_1"
        assert config.base_url == "https://proxy.example.com"
        assert config.identity_token() == "jwt"

    def test_missing_required_variable(self):
        env = {k: v for k, v in BASE_ENV.items() if k != "ANTHROPIC_SERVICE_ACCOUNT_ID"}
        with pytest.raises(FederationError, match="ANTHROPIC_SERVICE_ACCOUNT_ID"):
            FederationConfig.from_env(env)

    @pytest.mark.parametrize("name", ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"])
    def test_key_that_would_shadow_federation(self, name):
        with pytest.raises(FederationError, match=name):
            FederationConfig.from_env({**BASE_ENV, name: "sk-ant-x"})

    def test_blank_key_does_not_block(self):
        assert FederationConfig.from_env({**BASE_ENV, "ANTHROPIC_API_KEY": ""}) is not None


class TestIdentityTokenSource:
    def test_file_is_reread_on_every_exchange(self, tmp_path):
        token_file = tmp_path / "jwt"
        token_file.write_text("first\n")
        source = identity_token_source({"ANTHROPIC_IDENTITY_TOKEN_FILE": str(token_file)})
        assert source() == "first"
        token_file.write_text("second")
        assert source() == "second"

    def test_missing_file(self, tmp_path):
        source = identity_token_source({"ANTHROPIC_IDENTITY_TOKEN_FILE": str(tmp_path / "nope")})
        with pytest.raises(FederationError, match="ANTHROPIC_IDENTITY_TOKEN_FILE"):
            source()

    def test_falls_back_to_github(self):
        env = {"ACTIONS_ID_TOKEN_REQUEST_URL": "https://gh/token?v=1", "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "req"}
        with patch("federation._request_json", return_value={"value": "gh-jwt"}):
            assert identity_token_source(env)() == "gh-jwt"


class TestGitHubIdentityToken:
    def test_requests_anthropic_audience(self):
        env = {"ACTIONS_ID_TOKEN_REQUEST_URL": "https://gh/token?v=1", "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "req"}
        with patch("federation._request_json", return_value={"value": "gh-jwt"}) as request:
            assert github_identity_token(env) == "gh-jwt"
        url, body, headers = request.call_args.args
        assert url == "https://gh/token?v=1&audience=https%3A%2F%2Fapi.anthropic.com"
        assert body is None
        assert headers == {"Authorization": "Bearer req"}

    def test_without_id_token_permission(self):
        with pytest.raises(FederationError, match="id-token: write"):
            github_identity_token({})


class TestFederatedToken:
    def test_exchange_body(self):
        with patch("federation._request_json", return_value={"access_token": "sk-ant-oat01-a", "expires_in": 600}) as r:
            assert FederatedToken(make_config(workspace_id="wrkspc_1")).exchange() == ("sk-ant-oat01-a", 600)
        url, body, _ = r.call_args.args
        assert url == "https://api.anthropic.com/v1/oauth/token"
        assert body == {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": "jwt",
            "federation_rule_id": "fdrl_1",
            "organization_id": "org-uuid",
            "service_account_id": "svac_1",
            "workspace_id": "wrkspc_1",
        }

    def test_workspace_omitted_when_unset(self):
        with patch("federation._request_json", return_value={"access_token": "t", "expires_in": 600}) as r:
            FederatedToken(make_config()).exchange()
        assert "workspace_id" not in r.call_args.args[1]

    def test_missing_access_token(self):
        with patch("federation._request_json", return_value={}):
            with pytest.raises(FederationError, match="access_token"):
                FederatedToken(make_config()).exchange()

    def test_cached_until_refresh_margin(self):
        now = [1000.0]
        token = FederatedToken(make_config(), clock=lambda: now[0])
        responses = iter([{"access_token": "t1", "expires_in": 600}, {"access_token": "t2", "expires_in": 600}])
        with patch("federation._request_json", side_effect=lambda *_: next(responses)):
            assert token.get() == "t1"
            now[0] += 600 - 121
            assert token.get() == "t1"
            now[0] += 2
            assert token.get() == "t2"

    def test_short_lifetime_refreshes_at_half(self):
        now = [0.0]
        token = FederatedToken(make_config(), clock=lambda: now[0])
        responses = iter([{"access_token": "t1", "expires_in": 60}, {"access_token": "t2", "expires_in": 60}])
        with patch("federation._request_json", side_effect=lambda *_: next(responses)):
            token.get()
            now[0] = 29
            assert token.get() == "t1"
            now[0] = 30
            assert token.get() == "t2"


class TestRefreshAuthToken:
    @pytest.fixture(autouse=True)
    def reset_module(self, monkeypatch):
        monkeypatch.setattr(federation, "_token", None)
        monkeypatch.setattr(federation, "_loaded", False)
        for name in [*BASE_ENV, "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_IDENTITY_TOKEN_FILE"]:
            monkeypatch.delenv(name, raising=False)

    def test_noop_without_federation(self):
        assert federation.refresh_auth_token() is False
        assert "ANTHROPIC_AUTH_TOKEN" not in os.environ

    def test_sets_auth_token_and_drops_blank_key(self, monkeypatch):
        for name, value in BASE_ENV.items():
            monkeypatch.setenv(name, value)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "")
        with patch("federation._request_json", return_value={"access_token": "sk-ant-oat01-a", "expires_in": 600}):
            assert federation.refresh_auth_token() is True
            # The token now in the environment must not read as a shadowing key on later calls
            assert federation.refresh_auth_token() is True
        assert os.environ["ANTHROPIC_AUTH_TOKEN"] == "sk-ant-oat01-a"
        assert "ANTHROPIC_API_KEY" not in os.environ
