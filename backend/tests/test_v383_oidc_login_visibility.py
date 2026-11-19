from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_login_button_is_always_visible_when_oidc_is_unavailable():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert '<button id="login" type="button">Se connecter</button>' in html
    assert "$('#login').classList.remove('hidden')" in html
    assert "$('#login').classList.toggle('hidden'" not in html


def test_oidc_script_loading_failures_are_reported_to_the_user():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'onerror="window.__dikeviaAuthScriptError=' in html
    assert "Configuration OIDC absente" in html
    assert "Module OIDC non initialisé" in html
    assert "Module OIDC indisponible" in html


def test_login_click_handles_a_missing_oidc_module_without_hiding_the_button():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "if(!auth||typeof auth.login!=='function')" in html
    assert "Vérifiez le fichier /static/auth-config.js." in html
    assert "Vérifiez le fichier /static/oidc-auth.js." in html


def test_api_unauthorized_response_returns_user_to_login_screen():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "if(response.status===401){token=null;showAuth(" in html
    assert "Votre session a expiré ou n’est plus valide." in html
