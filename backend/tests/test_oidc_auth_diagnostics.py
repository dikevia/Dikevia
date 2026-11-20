import logging

import jwt
import pytest
from fastapi import HTTPException

from app import security


class BrokenJWKSClient:
    def get_signing_key_from_jwt(self, token):
        raise jwt.InvalidAudienceError("sensitive provider detail must not be logged")


def test_oidc_validation_logs_exception_type_without_token_or_claims(monkeypatch, caplog):
    monkeypatch.setattr(security.settings, "oidc_issuer", "https://identity.example/realms/cfdt")
    monkeypatch.setattr(security.settings, "oidc_audience", "cfdt-juris-api")
    monkeypatch.setattr(security.settings, "oidc_jwks_url", "https://identity.example/realms/cfdt/certs")
    monkeypatch.setattr(security.settings, "oidc_algorithms", "RS256")
    monkeypatch.setattr(security, "jwks_client", lambda _url: BrokenJWKSClient())

    bearer = "test-bearer-token-must-never-appear-in-logs"
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        with pytest.raises(HTTPException) as exc:
            security.verify_access_token(bearer)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Jeton invalide ou expiré."
    assert "reason=aud_mismatch" in caplog.text
    assert "sensitive provider detail" not in caplog.text
    assert bearer not in caplog.text
