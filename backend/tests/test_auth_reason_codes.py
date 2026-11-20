"""Tests for safe OIDC rejection reason codes; no real identity provider or secrets."""
import asyncio
import logging
import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from jwt import exceptions as jwt_exc

from app import dependencies, security

ISSUER = "https://idp.example.test/realms/cfdt"
AUDIENCE = "cfdt-juris-api"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
SETTINGS = SimpleNamespace(
    oidc_issuer=ISSUER,
    oidc_audience=AUDIENCE,
    oidc_jwks_url="https://idp.example.test/certs",
    oidc_algorithms="RS256",
)


class FakeJwks:
    def __init__(self, error=None):
        self.error = error

    def get_signing_key_from_jwt(self, token):
        if self.error:
            raise self.error
        return SimpleNamespace(key=KEY.public_key())


def make_token(key=KEY, **overrides):
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "user-secret-subject",
        "iat": now,
        "exp": now + 300,
        "email": "agent@example.test",
    }
    claims.update(overrides)
    claims = {name: value for name, value in claims.items() if value is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "k1"})


@pytest.fixture(autouse=True)
def oidc_settings_and_jwks(monkeypatch):
    monkeypatch.setattr(security, "settings", SETTINGS)
    monkeypatch.setattr(security, "jwks_client", lambda _url: FakeJwks())


def reject(token, expected_status=401, caplog=None):
    with pytest.raises(HTTPException) as ctx:
        security.verify_access_token(token)
    assert ctx.value.status_code == expected_status
    if caplog is not None:
        text = caplog.text
        for secret in (token, "user-secret-subject", "agent@example.test"):
            if secret:
                assert secret not in text
                assert secret not in str(ctx.value.detail)
    return ctx.value


def test_valid_token_is_accepted():
    principal = security.verify_access_token(make_token())
    assert principal.subject == "user-secret-subject"
    assert principal.issuer == ISSUER


def test_audience_mismatch(caplog):
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(aud="account"), caplog=caplog)
    assert "reason=aud_mismatch" in caplog.text


def test_audience_list_with_expected_value_is_accepted():
    security.verify_access_token(make_token(aud=["account", AUDIENCE]))


def test_audience_missing(caplog):
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(aud=None), caplog=caplog)
    assert "reason=missing_claim_aud" in caplog.text


def test_issuer_mismatch(caplog):
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(iss=ISSUER + "/"), caplog=caplog)
    assert "reason=iss_mismatch" in caplog.text


def test_subject_missing(caplog):
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(sub=None), caplog=caplog)
    assert "reason=missing_claim_sub" in caplog.text


def test_subject_blank(caplog):
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(sub="   "), caplog=caplog)
    assert "reason=sub_invalid" in caplog.text


def test_expired(caplog):
    now = int(time.time())
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(iat=now - 700, exp=now - 400), caplog=caplog)
    assert "reason=expired" in caplog.text


def test_expiry_within_30_second_leeway_is_accepted():
    now = int(time.time())
    security.verify_access_token(make_token(iat=now - 400, exp=now - 20))


def test_expiry_beyond_30_second_leeway_is_rejected(caplog):
    now = int(time.time())
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(iat=now - 400, exp=now - 40), caplog=caplog)
    assert "reason=expired" in caplog.text


def test_future_iat_within_30_second_leeway_is_accepted():
    now = int(time.time())
    security.verify_access_token(make_token(iat=now + 20, exp=now + 320))


def test_future_iat_beyond_30_second_leeway_is_rejected(caplog):
    now = int(time.time())
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(iat=now + 40, exp=now + 340), caplog=caplog)
    assert "reason=not_yet_valid" in caplog.text


def test_lifetime_excessive(caplog):
    now = int(time.time())
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(iat=now, exp=now + 3600), caplog=caplog)
    assert "reason=lifetime_excessive" in caplog.text


def test_lifetime_at_limit_is_accepted():
    now = int(time.time())
    security.verify_access_token(make_token(iat=now, exp=now + 900))


def test_lifetime_invalid(caplog):
    now = int(time.time())
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(iat=now + 10, exp=now + 5), caplog=caplog)
    assert "reason=lifetime_invalid" in caplog.text


def test_bad_signature(caplog):
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(key=OTHER_KEY), caplog=caplog)
    assert "reason=bad_signature" in caplog.text


def test_malformed_token(caplog):
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject("pas.un.jwt", caplog=caplog)
    assert "reason=malformed_token" in caplog.text


def test_algorithm_not_allowed(caplog):
    token = jwt.encode(
        {"iss": ISSUER, "aud": AUDIENCE, "sub": "x", "iat": 1, "exp": 2},
        "k" * 40,
        algorithm="HS256",
    )
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(token, caplog=caplog)
    assert "reason=alg_not_allowed" in caplog.text


def test_token_too_long(caplog):
    token = "a" * (security.MAX_BEARER_TOKEN_LENGTH + 1)
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(token, caplog=caplog)
    assert "reason=token_empty_or_too_long" in caplog.text


def test_empty_token(caplog):
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject("", caplog=caplog)
    assert "reason=token_empty_or_too_long" in caplog.text


def test_jwks_unavailable_is_503_not_401(monkeypatch, caplog):
    monkeypatch.setattr(
        security,
        "jwks_client",
        lambda _url: FakeJwks(jwt_exc.PyJWKClientConnectionError("private timeout detail")),
    )
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        exc = reject(make_token(), expected_status=503, caplog=caplog)
    assert "reason=jwks_unavailable" in caplog.text
    assert "private timeout detail" not in caplog.text
    assert exc.detail == "Service d'identité momentanément indisponible. Réessayez."


def test_unknown_kid_is_401(monkeypatch, caplog):
    monkeypatch.setattr(
        security,
        "jwks_client",
        lambda _url: FakeJwks(jwt_exc.PyJWKClientError("private kid detail")),
    )
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(), caplog=caplog)
    assert "reason=jwks_key_not_found" in caplog.text
    assert "private kid detail" not in caplog.text


def test_internal_error_logs_class_name_only(monkeypatch, caplog):
    monkeypatch.setattr(
        security,
        "jwks_client",
        lambda _url: FakeJwks(TypeError("private internal detail")),
    )
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        reject(make_token(), caplog=caplog)
    assert "reason=internal_TypeError" in caplog.text
    assert "private internal detail" not in caplog.text


def test_missing_configuration_is_503(monkeypatch, caplog):
    empty = SimpleNamespace(**{**SETTINGS.__dict__, "oidc_audience": ""})
    monkeypatch.setattr(security, "settings", empty)
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        exc = reject(make_token(), expected_status=503, caplog=caplog)
    assert "reason=oidc_not_configured" in caplog.text
    assert exc.detail == "Authentification OIDC non configurée."


def test_unsafe_algorithm_configuration_is_503(monkeypatch, caplog):
    unsafe = SimpleNamespace(**{**SETTINGS.__dict__, "oidc_algorithms": "HS256"})
    monkeypatch.setattr(security, "settings", unsafe)
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        exc = reject(make_token(), expected_status=503, caplog=caplog)
    assert "reason=oidc_algorithms_unsafe" in caplog.text
    assert exc.detail == "Configuration des algorithmes OIDC non sûre."


def test_client_message_stays_neutral(caplog):
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        exc = reject(make_token(aud="account"), caplog=caplog)
    assert exc.detail == "Jeton invalide ou expiré."


def test_bearer_missing_is_logged_without_secrets(caplog):
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        with pytest.raises(HTTPException) as ctx:
            asyncio.run(dependencies.get_principal(None))
    assert ctx.value.status_code == 401
    assert ctx.value.detail == "Authentification requise."
    assert "reason=bearer_missing" in caplog.text
    assert "user-secret-subject" not in caplog.text


def test_wrong_authorization_scheme_is_rejected(caplog):
    credentials = HTTPAuthorizationCredentials(scheme="Basic", credentials="do-not-log-this")
    with caplog.at_level(logging.WARNING, logger="dikevia.auth"):
        with pytest.raises(HTTPException) as ctx:
            asyncio.run(dependencies.get_principal(credentials))
    assert ctx.value.status_code == 401
    assert ctx.value.detail == "Authentification requise."
    assert "reason=bearer_missing" in caplog.text
    assert "do-not-log-this" not in caplog.text
