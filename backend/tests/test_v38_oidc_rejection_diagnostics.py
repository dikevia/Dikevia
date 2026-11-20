import logging
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException

from app import security


class FakeSigningKey:
    key = "test-public-key"


class FakeJwksClient:
    def get_signing_key_from_jwt(self, token):
        return FakeSigningKey()


def configure_oidc(monkeypatch):
    monkeypatch.setattr(
        security,
        "settings",
        SimpleNamespace(
            oidc_issuer="https://issuer.example/realms/cfdt",
            oidc_audience="cfdt-juris-api",
            oidc_jwks_url="https://issuer.example/jwks",
            oidc_algorithms="RS256",
        ),
    )


def test_audience_rejection_is_logged_without_token_or_exception_details(monkeypatch, caplog):
    configure_oidc(monkeypatch)
    monkeypatch.setattr(security, "jwks_client", lambda _url: FakeJwksClient())

    def reject_decode(*_args, **_kwargs):
        raise jwt.InvalidAudienceError("sensitive internal detail")

    monkeypatch.setattr(security.jwt, "decode", reject_decode)
    bearer = "this-is-a-private-bearer-token"

    with caplog.at_level(logging.WARNING, logger="dikevia.security"):
        with pytest.raises(HTTPException) as error:
            security.verify_access_token(bearer)

    assert error.value.status_code == 401
    assert error.value.detail == "Jeton invalide ou expiré."
    assert "reason=audience_mismatch" in caplog.text
    assert "InvalidAudienceError" in caplog.text
    assert bearer not in caplog.text
    assert "sensitive internal detail" not in caplog.text


def test_jwks_failure_has_a_distinct_non_sensitive_diagnostic(monkeypatch, caplog):
    configure_oidc(monkeypatch)

    class UnavailableJwksClient:
        def get_signing_key_from_jwt(self, _token):
            raise RuntimeError("private network detail")

    monkeypatch.setattr(
        security,
        "jwks_client",
        lambda _url: UnavailableJwksClient(),
    )

    with caplog.at_level(logging.WARNING, logger="dikevia.security"):
        with pytest.raises(HTTPException):
            security.verify_access_token("private-token")

    assert "reason=jwks_unavailable" in caplog.text
    assert "RuntimeError" in caplog.text
    assert "private network detail" not in caplog.text
    assert "private-token" not in caplog.text
