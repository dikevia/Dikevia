from pathlib import Path


def test_startup_reports_invitation_readiness_without_logging_secrets():
    source = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text()
    start = source.index("DIKEVIA_DIAGNOSTIC INVITATION_PROVISIONING")
    end = source.index("\n    )", start) + len("\n    )")
    diagnostic = source[start:end]
    assert "smtp_configured=%s" in diagnostic
    assert "keycloak_admin_configured=%s" in diagnostic
    assert "settings.smtp_host and settings.smtp_from" in diagnostic
    assert "settings.keycloak_admin_base_url and settings.keycloak_admin_client_secret" in diagnostic
    assert "settings.smtp_password" not in diagnostic
    assert "settings.keycloak_admin_client_secret," not in diagnostic
