from pathlib import Path


def test_startup_reports_invitation_readiness_without_logging_secrets():
    source = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text()
    assert "DIKEVIA_DIAGNOSTIC INVITATION_PROVISIONING" in source
    assert "smtp_configured=%s" in source
    assert "keycloak_admin_configured=%s" in source
    assert "settings.smtp_host and settings.smtp_from" in source
    assert "settings.keycloak_admin_base_url and settings.keycloak_admin_client_secret" in source
    assert "settings.smtp_password" not in source[source.index("DIKEVIA_DIAGNOSTIC INVITATION_PROVISIONING"):]
    assert "settings.keycloak_admin_client_secret," not in source[source.index("DIKEVIA_DIAGNOSTIC INVITATION_PROVISIONING"):]
