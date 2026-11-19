import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_keycloak_realm_has_public_pkce_client_and_api_audience():
    realm = json.loads((ROOT / "deploy/keycloak/realm-cfdt.template.json").read_text())
    assert realm["realm"] == "cfdt"
    assert realm["registrationAllowed"] is False
    client = next(c for c in realm["clients"] if c["clientId"] == "cfdt-juris-web")
    assert client["publicClient"] is True
    assert client["standardFlowEnabled"] is True
    assert client["implicitFlowEnabled"] is False
    assert client["directAccessGrantsEnabled"] is False
    assert "cfdt-juris-api-audience" in client["defaultClientScopes"]
    assert client["attributes"]["pkce.code.challenge.method"] == "S256"

    android = next(c for c in realm["clients"] if c["clientId"] == "dikevia-android")
    assert android["publicClient"] is True
    assert android["standardFlowEnabled"] is True
    assert android["implicitFlowEnabled"] is False
    assert android["directAccessGrantsEnabled"] is False
    assert android["redirectUris"] == ["fr.dikevia.commercial:/oauth2redirect"]
    assert android["attributes"]["pkce.code.challenge.method"] == "S256"
    assert "cfdt-juris-api-audience" in android["defaultClientScopes"]

    imported = json.loads((ROOT / "deploy/keycloak/import/realm-cfdt.json").read_text())
    imported_android = next(c for c in imported["clients"] if c["clientId"] == "dikevia-android")
    assert imported_android["redirectUris"] == android["redirectUris"]
    assert imported_android["attributes"]["pkce.code.challenge.method"] == "S256"
    assert "cfdt-juris-api-audience" in imported_android["defaultClientScopes"]
    scope = next(s for s in realm["clientScopes"] if s["name"] == "cfdt-juris-api-audience")
    mapper = scope["protocolMappers"][0]
    assert mapper["protocolMapper"] == "oidc-audience-mapper"
    assert mapper["config"]["included.custom.audience"] == "cfdt-juris-api"
    assert mapper["config"]["access.token.claim"] == "true"
    assert mapper["config"]["id.token.claim"] == "false"


def test_keycloak_compose_uses_separate_database_and_pinned_image():
    compose = (ROOT / "deploy/docker-compose.yml").read_text()
    assert "quay.io/keycloak/keycloak:26.8.2" in compose
    assert "keycloak-db:" in compose
    assert "keycloak_data:/var/lib/postgresql/data" in compose
    assert "./keycloak/import:/opt/keycloak/data/import:ro" in compose
    assert '"${KEYCLOAK_BIND_ADDRESS:-127.0.0.1}:${KEYCLOAK_PORT:-8081}:8080"' in compose


def test_render_script_never_generates_a_browser_secret():
    script = (ROOT / "scripts/render_keycloak_config.py").read_text()
    assert "client_secret" not in script
    assert '"client_id": "cfdt-juris-web"' in script
    assert '"redirect_uri": app + "/"' in script
