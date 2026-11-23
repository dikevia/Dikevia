import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_render_api_image_uses_origin_scoped_oidc_configuration():
    dockerfile = (ROOT / "Dockerfile").read_text()
    auth = (ROOT / "frontend/auth-config.render.js").read_text()
    assert "COPY frontend/auth-config.render.js /srv/frontend/auth-config.js" in dockerfile
    assert 'const appOrigin = window.location.origin' in auth
    assert '"redirect_uri": appOrigin + "/"' in auth
    assert '"silent_redirect_uri": appOrigin + "/static/silent-check-sso.html"' in auth
    assert "cfdt-juris-web" in auth


def test_render_keycloak_realm_and_api_redirect_origins_match():
    realm = json.loads((ROOT / "deploy/keycloak/realm-cfdt.render.json").read_text())
    client = next(item for item in realm["clients"] if item["clientId"] == "cfdt-juris-web")
    app_origin = "https://dikevia-commercial-api-l2r8.onrender.com"
    assert client["redirectUris"] == [app_origin + "/*"]
    assert client["webOrigins"] == [app_origin]
    assert client["attributes"]["post.logout.redirect.uris"] == app_origin + "/*"


def test_render_blueprint_uses_free_frankfurt_services_and_no_committed_secrets():
    blueprint = (ROOT / "render.yaml").read_text()
    assert blueprint.count("plan: free") == 2
    assert blueprint.count("region: frankfurt") == 2
    for key in ("DATABASE_URL", "LEGAL_CORPUS_INGEST_DATABASE_URL", "PLATFORM_ADMIN_DATABASE_URL",
                "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AI_API_KEY", "KC_DB_URL", "KC_DB_PASSWORD"):
        assert f"key: {key}\n        sync: false" in blueprint
    assert "generateValue: true" in blueprint
    assert "CHANGE_ME" not in blueprint


def test_render_keycloak_container_uses_expected_version_and_health_support():
    dockerfile = (ROOT / "deploy/keycloak/Dockerfile").read_text()
    assert dockerfile.startswith("FROM quay.io/keycloak/keycloak:26.8.2")
    assert "KC_HEALTH_ENABLED=true" in dockerfile
    assert "KC_PROXY_HEADERS=xforwarded" in dockerfile
