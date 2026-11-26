"""Configuration guards for the opt-in Auth0 server-side session mode."""
import pytest

from app.config import Settings, validate_runtime_configuration


def _auth0_session_settings(**overrides):
    values = dict(
        app_env="test",
        oidc_provider="auth0",
        oidc_server_sessions_enabled=True,
        oidc_client_id="public-spa-client",
        oidc_issuer="https://tenant.auth0.com/",
        oidc_audience="https://api.example",
        oidc_jwks_url="https://tenant.auth0.com/.well-known/jwks.json",
        oidc_authorization_audience="https://api.example",
        oidc_redirect_uri="https://app.example/",
        oidc_session_encryption_key=bytes(range(32)).hex(),
        oidc_scopes="openid profile email",
    )
    values.update(overrides)
    return Settings(**values)


def test_auth0_server_sessions_require_refresh_token_scope():
    with pytest.raises(RuntimeError, match="offline_access"):
        validate_runtime_configuration(_auth0_session_settings())
    validate_runtime_configuration(_auth0_session_settings(
        oidc_scopes="openid profile email offline_access"
    ))


def test_server_sessions_reject_missing_or_invalid_encryption_key():
    with pytest.raises(RuntimeError, match="OIDC_SESSION_ENCRYPTION_KEY"):
        validate_runtime_configuration(_auth0_session_settings(oidc_session_encryption_key="short"))
    with pytest.raises(RuntimeError, match="OIDC_REDIRECT_URI"):
        validate_runtime_configuration(_auth0_session_settings(oidc_redirect_uri="http://app.example/"))
