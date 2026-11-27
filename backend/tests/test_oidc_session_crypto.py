from types import SimpleNamespace

import pytest

from app import auth_session_crypto as crypto


def test_encryption_key_accepts_hex_and_urlsafe_base64():
    import base64
    key = bytes(range(32))
    assert crypto.decode_encryption_key(key.hex()) == key
    assert crypto.decode_encryption_key(base64.urlsafe_b64encode(key).decode()) == key


@pytest.mark.parametrize("value", ["", "short", "00" * 31, "zz" * 32])
def test_encryption_key_rejects_invalid_lengths_or_encoding(value):
    with pytest.raises(ValueError):
        crypto.decode_encryption_key(value)


def test_session_values_are_authenticated_and_purpose_bound(monkeypatch):
    key = bytes(range(32))
    monkeypatch.setattr(crypto, "settings", SimpleNamespace(oidc_session_encryption_key=key.hex()))
    encrypted = crypto.encrypt_session_value("refresh-token-value", "refresh")
    assert crypto.decrypt_session_value(encrypted, "refresh") == "refresh-token-value"
    with pytest.raises(Exception):
        crypto.decrypt_session_value(encrypted, "access")


def test_session_cookie_hash_is_one_way_and_validates_length():
    cookie = "x" * 48
    digest = crypto.hash_session_cookie(cookie)
    assert len(digest) == 64
    assert digest != cookie
    with pytest.raises(ValueError):
        crypto.hash_session_cookie("short")


def test_server_sessions_are_opt_in_and_require_encryption_and_https_redirect():
    from app.config import Settings, validate_runtime_configuration
    disabled = Settings(oidc_server_sessions_enabled=False)
    validate_runtime_configuration(disabled)

    enabled = Settings(
        oidc_server_sessions_enabled=True,
        oidc_provider="auth0",
        oidc_scopes="openid profile email offline_access",
        oidc_client_id="cfdt-juris-web",
        oidc_issuer="https://identity.example/realms/cfdt",
        oidc_audience="dikevia-api",
        oidc_jwks_url="https://identity.example/realms/cfdt/protocol/openid-connect/certs",
        oidc_redirect_uri="https://dikevia.example/",
        oidc_session_encryption_key=bytes(range(32)).hex(),
    )
    validate_runtime_configuration(enabled)
    with pytest.raises(RuntimeError, match="32 octets"):
        validate_runtime_configuration(enabled.model_copy(update={"oidc_session_encryption_key": "invalid"}))

def test_cookie_session_origin_guard_rejects_cross_origin_mutations(monkeypatch):
    from app import auth_sessions
    monkeypatch.setattr(auth_sessions, "settings", SimpleNamespace(
        cors_origins="https://app.example"
    ))
    auth_sessions.require_same_origin(SimpleNamespace(headers={"origin": "https://app.example"}))
    with pytest.raises(Exception):
        auth_sessions.require_same_origin(SimpleNamespace(headers={"origin": "https://attacker.example"}))
