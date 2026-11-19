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
    assert "sessionStorage.setItem('dikevia_oidc_state'" in auth
    assert "accessToken = data.access_token" in auth
    assert "localStorage" not in auth
    assert "refresh_token" not in auth


def test_example_oidc_config_has_no_client_secret():
    config = (ROOT / "frontend/auth-config.example.js").read_text(encoding="utf-8")
    assert "issuer:" in config and "client_id:" in config and "redirect_uri:" in config
    assert "client_secret:" not in config


def test_backend_api_version_is_current():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert 'version="3.38.0"' in main


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



def test_dossier_status_controls_reflect_privileged_roles():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "const canManageDossierStatus=role==='ORG_ADMIN'||role==='LEGAL_EDITOR'" in html
    assert "option.disabled=!canManageDossierStatus&&['VALIDE_HUMAINEMENT','CLOTURE'].includes(option.value)" in html
    assert "Validation et clôture réservées aux responsables habilités." in html


def test_pilot_chat_discloses_gemini_processing_and_requires_anonymized_cases():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "Google Gemini" in html
    assert "situations fictives ou anonymisées" in html
    assert "donnée médicale" in html
    assert "syndicale nominative" in html


def test_workspace_navigation_is_accessible_and_mobile_options_remain_visible():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'class="skip-link" href="#mainContent"' in html
    assert 'id="mainContent" tabindex="-1"' in html
    assert 'class="workspace-context"' in html
    assert 'aria-label="Navigation principale"' in html
    assert 'aria-current="page"' in html
    assert "grid-template-columns:repeat(2,minmax(0,1fr))" in html
    assert "@media(prefers-reduced-motion:reduce)" in html
    assert "b.setAttribute('aria-current','page')" in html


def test_commercial_workspace_has_polished_responsive_tables_and_forms():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert ".view>.heading{padding:2px 1px 17px" in html
    assert ".view .tablewrap th{position:sticky" in html
    assert ".view input[type=file]::file-selector-button" in html
    assert "#view-billing #billingCurrent" in html
    assert ".view .toolbar{display:grid;grid-template-columns:1fr 1fr" in html
    assert "@media(hover:none)" in html


def test_billing_screen_uses_validated_commercial_reference_prices():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "15 €" in html and "HT / mois" in html
    assert "170 €" in html and "HT / an" in html
    assert "790 €" in html and "5 accès" in html
    assert "19 € HT / mois" in html
    assert "9 à 15 € HT / mois / section" in html
    assert "20 questions par accès et par jour" in html
    assert "100 questions par section et par jour" in html
    assert "souscription en ligne sera activée après alignement" in html
    assert 'data-checkout="SYNDICAT_10"' not in html


def test_dikevia_oidc_globals_are_branded_and_auth_module_survives_missing_config():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    config = (ROOT / "frontend/auth-config.render.js").read_text(encoding="utf-8")
    assert "window.DIKEVIA_OIDC" in config
    assert "window.DIKEVIA_AUTH" in auth
    assert "window.CFDT_JURIS" not in auth + html + config
    root_auth = (ROOT / "oidc-auth.js").read_text(encoding="utf-8")
    root_config = (ROOT / "auth-config.js").read_text(encoding="utf-8")
    assert "window.CFDT_JURIS" not in root_auth + root_config
    assert "if (!cfg || !cfg.issuer || !cfg.client_id || !cfg.redirect_uri) return;" not in auth
    assert "Configuration OIDC Dikévia absente ou incomplète" in auth
    assert "const auth=window.DIKEVIA_AUTH||null;" in html
    assert "dikevia_oidc_state" in auth


def test_login_button_remains_visible_when_browser_auth_module_is_missing():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "$('#login').classList.remove('hidden')" in html
    assert "Le module OIDC navigateur Dikévia est introuvable" in html
