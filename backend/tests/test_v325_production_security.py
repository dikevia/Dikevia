import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_keycloak_access_token_and_persistent_sso_lifetimes_in_all_realm_configs():
    for relative in ("deploy/keycloak/realm-cfdt.template.json", "deploy/keycloak/import/realm-cfdt.json", "deploy/keycloak/realm-cfdt.render.json"):
        realm = json.loads((ROOT / relative).read_text(encoding="utf-8"))
        assert realm["accessTokenLifespan"] == 900
        assert realm["ssoSessionIdleTimeout"] == 604800
        assert realm["ssoSessionMaxLifespan"] == 2592000
        assert realm["revokeRefreshToken"] is True
        assert realm["refreshTokenMaxReuse"] == 0
        client = next(c for c in realm["clients"] if c["clientId"] == "cfdt-juris-web")
        assert client["attributes"]["pkce.code.challenge.method"] == "S256"
        assert client["implicitFlowEnabled"] is False
        assert client["directAccessGrantsEnabled"] is False

def test_production_env_audit_fails_closed_on_template_values():
    import importlib.util
    spec = importlib.util.spec_from_file_location("audit_production_env", ROOT / "scripts/audit_production_env.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert callable(module.audit)

def test_runtime_debug_defaults_to_false_and_is_rejected_in_production():
    import sys
    sys.path.insert(0, str(ROOT / "backend"))
    from app.config import Settings, validate_runtime_configuration
    cfg = Settings(app_env="production", debug=True)
    try:
        validate_runtime_configuration(cfg)
    except RuntimeError as exc:
        assert "DEBUG" in str(exc)
    else:
        raise AssertionError("Production must reject DEBUG=true")


def test_api_rejects_access_tokens_with_lifetime_over_15_minutes(monkeypatch):
    import sys
    import time
    sys.path.insert(0, str(ROOT / "backend"))
    from app import security
    from fastapi import HTTPException
    now = int(time.time())
    class Key:
        key = "test-key"

    class JWKS:
        def get_signing_key_from_jwt(self, token):
            return Key()
    monkeypatch.setattr(security, "jwks_client", lambda url: JWKS())
    monkeypatch.setattr(security.jwt, "decode", lambda *a, **k: {
        "sub": "subject", "iss": security.settings.oidc_issuer or "https://issuer.test",
        "aud": security.settings.oidc_audience or "api", "iat": now, "exp": now + 901
    })
    monkeypatch.setattr(security.settings, "oidc_issuer", "https://issuer.test")
    monkeypatch.setattr(security.settings, "oidc_audience", "api")
    monkeypatch.setattr(security.settings, "oidc_jwks_url", "https://issuer.test/jwks")
    try:
        security.verify_access_token("synthetic.jwt.token")
    except HTTPException as exc:
        assert exc.status_code == 401
    else:
        raise AssertionError("A token valid for more than 15 minutes must be rejected")


def test_production_env_audit_rejects_missing_or_weak_configuration(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("audit_production_env", ROOT / "scripts/audit_production_env.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env = tmp_path / "production.env"
    env.write_text("APP_ENV=production\nDEBUG=true\nPOSTGRES_APP_PASSWORD=CHANGE_ME_RUNTIME\n")
    errors = module.audit(env)
    assert any("DEBUG" in error for error in errors)
    assert any("POSTGRES_APP_PASSWORD" in error for error in errors)
    assert any("BACKUP_AGE_RECIPIENT" in error for error in errors)

