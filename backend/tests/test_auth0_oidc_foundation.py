"""Auth0 OIDC integration contracts; no live tenant or secrets are required."""
import time
from pathlib import Path
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException
from cryptography.hazmat.primitives.asymmetric import rsa

from app.config import Settings, validate_runtime_configuration
from app import security


ROOT = Path(__file__).resolve().parents[2]
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def production_base():
    return dict(
        app_env="production",
        database_url="postgresql://cfdt_juris_app:app@db/app",
        legal_corpus_ingest_database_url="postgresql://cfdt_juris_ingest:ingest@db/app",
        platform_admin_database_url="postgresql://cfdt_juris_platform_admin:platform@db/app",
        oidc_issuer="https://tenant.eu.auth0.com/",
        oidc_audience="urn:dikevia:api",
        oidc_jwks_url="https://tenant.eu.auth0.com/.well-known/jwks.json",
        oidc_provider="auth0",
        oidc_client_id="public-spa-client-id",
        oidc_authorization_audience="urn:dikevia:api",
        oidc_email_claim="https://dikevia.invalid/claims/email",
        oidc_email_verified_claim="https://dikevia.invalid/claims/email_verified",
        oidc_identity_compat_issuer="https://dikevia-identity-l2r8.onrender.com/realms/cfdt",
        oidc_identity_subject_prefix="auth0|",
        cors_origins="https://dikevia.example",
        aws_endpoint_url_s3="https://storage.example",
        aws_region="us-east-2",
        aws_access_key_id="test-access",
        aws_secret_access_key="test-secret",
        document_storage_bucket="cfdt-juris-documents",
    )


def test_auth0_production_configuration_requires_public_client_and_api_audience():
    base = production_base()
    validate_runtime_configuration(Settings(**base))

    missing_client = {**base, "oidc_client_id": ""}
    with pytest.raises(RuntimeError, match="OIDC_CLIENT_ID"):
        validate_runtime_configuration(Settings(**missing_client))

    missing_audience = {**base, "oidc_authorization_audience": ""}
    with pytest.raises(RuntimeError, match="OIDC_CLIENT_ID"):
        validate_runtime_configuration(Settings(**missing_audience))

    mismatched_audience = {**base, "oidc_authorization_audience": "urn:other:api"}
    with pytest.raises(RuntimeError, match="identique"):
        validate_runtime_configuration(Settings(**mismatched_audience))


def test_oidc_provider_scopes_and_compatibility_settings_are_validated():
    with pytest.raises(RuntimeError, match="OIDC_PROVIDER"):
        validate_runtime_configuration(Settings(oidc_provider="unknown"))
    with pytest.raises(RuntimeError, match="openid"):
        validate_runtime_configuration(Settings(oidc_scopes="profile email"))
    with pytest.raises(RuntimeError, match="doivent être configurés ensemble"):
        validate_runtime_configuration(Settings(oidc_identity_compat_issuer="https://old.example"))


class FakeJwks:
    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=KEY.public_key())


def test_auth0_token_claims_map_to_existing_keycloak_identity(monkeypatch):
    issuer = "https://tenant.eu.auth0.com/"
    audience = "urn:dikevia:api"
    old_issuer = "https://dikevia-identity-l2r8.onrender.com/realms/cfdt"
    settings = SimpleNamespace(
        oidc_issuer=issuer,
        oidc_audience=audience,
        oidc_jwks_url="https://tenant.eu.auth0.com/.well-known/jwks.json",
        oidc_algorithms="RS256",
        oidc_email_claim="https://dikevia.invalid/claims/email",
        oidc_email_verified_claim="https://dikevia.invalid/claims/email_verified",
        oidc_identity_compat_issuer=old_issuer,
        oidc_identity_subject_prefix="auth0|",
    )
    monkeypatch.setattr(security, "settings", settings)
    monkeypatch.setattr(security, "jwks_client", lambda _url: FakeJwks())

    now = int(time.time())
    token = jwt.encode(
        {
            "iss": issuer,
            "aud": audience,
            "sub": "auth0|existing-keycloak-user-uuid",
            "iat": now,
            "exp": now + 300,
            "https://dikevia.invalid/claims/email": "agent@example.test",
            "https://dikevia.invalid/claims/email_verified": True,
        },
        KEY,
        algorithm="RS256",
        headers={"kid": "auth0-key"},
    )

    principal = security.verify_access_token(token)
    assert principal.issuer == old_issuer
    assert principal.subject == "existing-keycloak-user-uuid"
    assert principal.email == "agent@example.test"
    assert principal.email_verified is True


def test_auth0_runtime_configuration_is_server_supplied_and_has_no_secret():
    main = (ROOT / "backend/app/main.py").read_text()
    frontend = (ROOT / "frontend/index.html").read_text()
    oidc = (ROOT / "frontend/oidc-auth.js").read_text()
    assert '@app.get("/auth-config.js"' in main
    assert "settings.oidc_client_id" in main
    assert "settings.oidc_authorization_audience" in main
    assert 'src="/auth-config.js"' in frontend
    assert "params.audience=cfg.audience" in oidc
    assert "client_secret" not in main[main.index('@app.get("/auth-config.js"'):main.index("orchestrator = LegalOrchestrator()")].lower()


def test_auth0_does_not_strip_unrelated_subjects(monkeypatch):
    issuer = "https://tenant.eu.auth0.com/"
    audience = "urn:dikevia:api"
    settings = SimpleNamespace(
        oidc_issuer=issuer,
        oidc_audience=audience,
        oidc_jwks_url="https://tenant.eu.auth0.com/.well-known/jwks.json",
        oidc_algorithms="RS256",
        oidc_email_claim="email",
        oidc_email_verified_claim="email_verified",
        oidc_identity_compat_issuer="https://legacy.example/realms/cfdt",
        oidc_identity_subject_prefix="auth0|",
    )
    monkeypatch.setattr(security, "settings", settings)
    monkeypatch.setattr(security, "jwks_client", lambda _url: FakeJwks())

    now = int(time.time())
    token = jwt.encode(
        {"iss": issuer, "aud": audience, "sub": "google-oauth2|unrelated",
         "iat": now, "exp": now + 300},
        KEY, algorithm="RS256",
    )
    with pytest.raises(HTTPException) as exc:
        security.verify_access_token(token)
    assert exc.value.status_code == 401


def test_auth0_without_legacy_mapping_keeps_native_auth0_subject(monkeypatch):
    issuer = "https://tenant.eu.auth0.com/"
    settings = SimpleNamespace(
        oidc_issuer=issuer,
        oidc_audience="urn:dikevia:api",
        oidc_jwks_url="https://tenant.eu.auth0.com/.well-known/jwks.json",
        oidc_algorithms="RS256",
        oidc_email_claim="email",
        oidc_email_verified_claim="email_verified",
        oidc_identity_compat_issuer="",
        oidc_identity_subject_prefix="",
    )
    monkeypatch.setattr(security, "settings", settings)
    monkeypatch.setattr(security, "jwks_client", lambda _url: FakeJwks())
    now = int(time.time())
    token = jwt.encode(
        {"iss": issuer, "aud": "urn:dikevia:api", "sub": "auth0|new-user",
         "iat": now, "exp": now + 300},
        KEY, algorithm="RS256",
    )
    principal = security.verify_access_token(token)
    assert principal.issuer == issuer
    assert principal.subject == "auth0|new-user"


def test_auth0_migration_keeps_database_roles_and_org_memberships_out_of_auth0():
    config = (ROOT / "backend/app/config.py").read_text()
    security_source = (ROOT / "backend/app/security.py").read_text()
    assert "oidc_identity_compat_issuer" in config
    assert "oidc_identity_subject_prefix" in config
    assert "canonical_subject = canonical_subject[len(compat_prefix):]" in security_source
    assert "platform_admins" not in (ROOT / "frontend/oidc-auth.js").read_text()
