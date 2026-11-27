from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_invitation_uses_auth0_universal_login_without_keycloak_provisioning():
    main = (ROOT / "backend/app/main.py").read_text()
    config = (ROOT / "backend/app/config.py").read_text()
    assert "KeycloakAdmin" not in main
    assert "keycloak_ready" not in main
    assert 'settings.oidc_provider == "auth0"' in main
    assert "Auth0 Universal Login handles authentication and any sign-up/email-verification flow enabled in the tenant." in main
    assert "await asyncio.to_thread(send_invitation_email" in main
    assert 'delivery = "SMTP_EMAIL_SENT"' in main
    assert 'result["invitation_token"] = token' in main  # manual fallback only
    assert 'if config.oidc_provider != "auth0"' in config


def test_role_change_is_tenant_scoped_audited_and_protects_last_admin():
    main = (ROOT / "backend/app/main.py").read_text()
    assert '@app.patch("/api/v1/organizations/me/members/{user_id}/role"' in main
    assert "Depends(require_org_admin)" in main
    assert "Impossible de retirer le dernier administrateur" in main
    assert "MEMBERSHIP_ROLE_CHANGED" in main
    assert "WHERE organization_id=$1::uuid AND user_id=$2::uuid" in main


def test_keycloak_admin_credentials_are_not_in_browser_assets():
    frontend = "\n".join(p.read_text(errors="ignore") for p in (ROOT / "frontend").glob("*.js"))
    assert "KEYCLOAK_ADMIN_CLIENT_SECRET" not in frontend


def test_auth0_invitation_configuration_keeps_smtp_and_redirect_requirements():
    env = (ROOT / "deploy/.env.example").read_text()
    assert "SMTP_HOST" in env and "SMTP_FROM" in env
    assert "INVITATION_BASE_URL" in env
