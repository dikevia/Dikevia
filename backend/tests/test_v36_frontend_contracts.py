from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_dashboard_exposes_required_workspace_sections():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    for fragment in (
        'id="view-overview"', 'id="view-documents"', 'id="view-collectivities"',
        'id="view-members"', 'id="view-ask"', 'id="orgSelect"', 'id="joinForm"',
        "'/api/v1/organizations'", "'/api/v1/documents'", "'/api/v1/collectivities'",
        "'/api/v1/organizations/me/members'", "'/api/v1/chat/ask'",
    ):
        assert fragment in html


def test_frontend_uses_oidc_pkce_and_does_not_persist_access_token():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    assert "code_challenge_method:'S256'" in auth
    assert "code_verifier:verifier" in auth
    assert "sessionStorage.setItem('cfdt_oidc_state'" in auth
    assert "accessToken = data.access_token" in auth
    assert "localStorage" not in auth
    assert "refresh_token" not in auth


def test_example_oidc_config_has_no_client_secret():
    config = (ROOT / "frontend/auth-config.example.js").read_text(encoding="utf-8")
    assert "issuer:" in config and "client_id:" in config and "redirect_uri:" in config
    assert "client_secret:" not in config


def test_backend_api_version_is_current():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert 'version="3.34.0"' in main


def test_frontend_static_assets_are_mounted_and_config_is_present():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'app.mount("/static", StaticFiles' in main
    assert '/static/auth-config.js' in html and '/static/oidc-auth.js' in html
    assert (ROOT / "frontend/auth-config.js").exists()


def test_v326_juris_chat_uses_existing_api_without_demo_or_local_token_storage():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'id="jurisMessages"' in html
    assert "api('/api/v1/chat/ask'" in html
    assert "verification_status" in html
    assert "Aucune réponse juridique de démonstration" in html
    assert "localStorage.setItem('cfdt_api_config'" not in html
    assert "marked.parse" not in html
    assert "textContent=text" in html



def test_juris_sources_display_the_matching_local_collectivity():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "src.collectivity" in html
    assert "src.local_document_type" in html


def test_chat_endpoint_uses_server_side_rate_limit_and_retry_after():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert "consume_chat_request(" in main
    assert "status_code=429" in main
    assert '"Retry-After"' in main
    migration = (ROOT / "database/migrations/017_chat_rate_limits.sql").read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "FORCE ROW LEVEL SECURITY" in migration
