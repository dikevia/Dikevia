import asyncio

from app.main import browser_oidc_configuration, settings


def test_runtime_oidc_configuration_is_valid_javascript(monkeypatch):
    monkeypatch.setattr(settings, "oidc_client_id", "cfdt-juris-web")
    monkeypatch.setattr(settings, "oidc_issuer", "https://identity.example/realms/cfdt")
    monkeypatch.setattr(settings, "oidc_scopes", "openid profile email")
    monkeypatch.setattr(settings, "oidc_authorization_audience", "")
    monkeypatch.setattr(settings, "oidc_audience", "dikevia-api")
    monkeypatch.setattr(settings, "oidc_server_sessions_enabled", False)
    monkeypatch.setattr(settings, "invitation_base_url", "https://dikevia.example")

    response = asyncio.run(browser_oidc_configuration())

    assert response.status_code == 200
    assert response.media_type == "application/javascript"
    script = response.body.decode("utf-8")
    assert "window.CFDT_JURIS_OIDC = Object.freeze({" in script
    assert 'issuer:"https://identity.example/realms/cfdt"' in script
    assert 'client_id:"cfdt-juris-web"' in script
    assert 'audience:"dikevia-api"' in script
    assert "server_sessions_enabled:false" in script
    assert script.rstrip().endswith("});")
