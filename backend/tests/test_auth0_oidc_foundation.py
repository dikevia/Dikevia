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


def test_auth0_is_the_default_oidc_provider():
    assert Settings(_env_file=None).oidc_provider == "auth0"


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
    with pytest.raises(RuntimeError, match="OIDC_IDENTITY_SUBJECT_PREFIX"):
        validate_runtime_configuration(Settings(
            app_env="production", oidc_provider="auth0",
            oidc_issuer="https://tenant.auth0.com/", oidc_audience="urn:api",
            oidc_jwks_url="https://tenant.auth0.com/.well-known/jwks.json",
            oidc_client_id="client", oidc_authorization_audience="urn:api",
            oidc_identity_compat_issuer="https://old.example",
            oidc_identity_subject_prefix="",
        ))


class FakeJwks:
    def get_signing_key_from_jwt(self, token):
        return SimpleNamespace(key=KEY.public_key())


def test_auth0_access_token_retains_native_subject_for_database_checked_mapping(monkeypatch):
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
            "sub": "auth0|auth0-internal-id",
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
    assert principal.issuer == issuer
    assert principal.subject == "auth0|auth0-internal-id"
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
    assert "scope:cfg.scopes||'openid profile email',state,nonce" in oidc
    assert "data.id_token" in oidc
    assert "X-OIDC-ID-Token" in oidc
    assert "X-OIDC-ID-Token" in frontend
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
    principal = security.verify_access_token(token)
    assert principal.issuer == issuer
    assert principal.subject == "google-oauth2|unrelated"


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
        oidc_identity_subject_prefix="auth0|",
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
    dependencies_source = (ROOT / "backend/app/dependencies.py").read_text()
    assert "users WHERE oidc_issuer=$1 AND oidc_subject=$2 AND status='ACTIVE'" in dependencies_source
    assert "verify_identity_token" in dependencies_source
    assert "platform_admins" not in (ROOT / "frontend/oidc-auth.js").read_text()


def test_auth0_id_token_is_signature_audience_issuer_and_subject_bound(monkeypatch):
    issuer = "https://tenant.eu.auth0.com/"
    client_id = "public-spa-client-id"
    monkeypatch.setattr(security, "settings", SimpleNamespace(
        oidc_issuer=issuer, oidc_client_id=client_id,
        oidc_jwks_url=issuer + ".well-known/jwks.json",
        oidc_algorithms="RS256",
    ))
    monkeypatch.setattr(security, "jwks_client", lambda _url: FakeJwks())
    now = int(time.time())
    principal = security.Principal(subject="auth0|new-user", issuer=issuer)
    token = jwt.encode(
        {"iss": issuer, "aud": client_id, "sub": principal.subject,
         "iat": now, "exp": now + 600,
         "email": "agent@example.test", "email_verified": True},
        KEY, algorithm="RS256",
    )
    verified = security.verify_identity_token(token, principal)
    assert verified.subject == principal.subject
    assert verified.issuer == issuer
    assert verified.email == "agent@example.test"
    assert verified.email_verified is True

    mismatched = jwt.encode(
        {"iss": issuer, "aud": client_id, "sub": "auth0|other-user",
         "iat": now, "exp": now + 600},
        KEY, algorithm="RS256",
    )
    with pytest.raises(HTTPException):
        security.verify_identity_token(mismatched, principal)


class _FakeTransaction:
    async def __aenter__(self):
        return self
    async def __aexit__(self, *_args):
        return False


class _FakeConnection:
    def __init__(self, expected_issuer, expected_subject, exists):
        self.expected_issuer = expected_issuer
        self.expected_subject = expected_subject
        self.exists = exists
        self.settings = {}
    def transaction(self):
        return _FakeTransaction()
    async def execute(self, query, value):
        if "app.oidc_issuer" in query:
            self.settings["app.oidc_issuer"] = value
        elif "app.oidc_subject" in query:
            self.settings["app.oidc_subject"] = value
    async def fetchrow(self, _query, issuer, subject):
        assert self.settings.get("app.oidc_issuer") == issuer
        assert self.settings.get("app.oidc_subject") == subject
        if self.exists and issuer == self.expected_issuer and subject == self.expected_subject:
            return {"id": "internal-user-id"}
        return None


class _FakeAcquire:
    def __init__(self, connection):
        self.connection = connection
    async def __aenter__(self):
        return self.connection
    async def __aexit__(self, *_args):
        return False


class _FakePool:
    def __init__(self, connection):
        self.connection = connection
    def acquire(self):
        return _FakeAcquire(self.connection)


@pytest.mark.parametrize("exists,expected_issuer,expected_subject", [
    (True, "https://legacy.example/realms/cfdt", "legacy-user-123"),
    (False, "https://tenant.eu.auth0.com/", "auth0|legacy-user-123"),
])
def test_auth0_legacy_mapping_requires_exact_existing_database_identity(
    monkeypatch, exists, expected_issuer, expected_subject
):
    from app import dependencies
    legacy_issuer = "https://legacy.example/realms/cfdt"
    conn = _FakeConnection(legacy_issuer, "legacy-user-123", exists)
    monkeypatch.setattr(dependencies, "get_pool", lambda: _FakePool(conn))
    monkeypatch.setattr(dependencies, "settings", SimpleNamespace(
        oidc_provider="auth0",
        oidc_identity_compat_issuer=legacy_issuer,
        oidc_identity_subject_prefix="auth0|",
    ))
    principal = security.Principal(
        subject="auth0|legacy-user-123",
        issuer="https://tenant.eu.auth0.com/",
        email="agent@example.test",
        email_verified=True,
    )
    mapped = __import__("asyncio").run(dependencies._resolve_auth0_legacy_identity(principal))
    assert mapped.issuer == expected_issuer
    assert mapped.subject == expected_subject
    assert mapped.email == principal.email
    assert mapped.email_verified is True


def test_auth0_unverified_or_missing_email_is_denied():
    from app.dependencies import _require_verified_auth0_email

    verified = security.Principal(
        subject="auth0|user", issuer="https://tenant.eu.auth0.com/",
        email="agent@example.test", email_verified=True,
    )
    assert _require_verified_auth0_email(verified) == verified

    unverified = security.Principal(
        subject="auth0|user", issuer="https://tenant.eu.auth0.com/",
        email="agent@example.test", email_verified=False,
    )
    with pytest.raises(HTTPException) as exc:
        _require_verified_auth0_email(unverified)
    assert exc.value.status_code == 403

    no_email = security.Principal(
        subject="auth0|user", issuer="https://tenant.eu.auth0.com/",
        email=None, email_verified=False,
    )
    with pytest.raises(HTTPException) as exc:
        _require_verified_auth0_email(no_email)
    assert exc.value.status_code == 403


def test_auth0_migration_refuses_existing_subject_with_different_email():
    import runpy

    migration = runpy.run_path(str(ROOT / "scripts" / "migrate_keycloak_users_to_auth0.py"))
    validate = migration["validate_existing_auth0_user"]

    validate(None, "auth0|legacy-subject", "agent@example.org")
    validate(
        {"user_id": "auth0|legacy-subject", "email": "Agent@Example.org"},
        "auth0|legacy-subject",
        "agent@example.org",
    )
    with pytest.raises(RuntimeError, match="autre adresse"):
        validate(
            {"user_id": "auth0|legacy-subject", "email": "different@example.org"},
            "auth0|legacy-subject",
            "agent@example.org",
        )
    with pytest.raises(RuntimeError, match="incohérent"):
        validate(
            {"user_id": "auth0|other-subject", "email": "agent@example.org"},
            "auth0|legacy-subject",
            "agent@example.org",
        )
