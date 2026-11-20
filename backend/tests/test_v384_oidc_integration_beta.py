from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_login_button_is_visible_without_oidc_module():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert '<button id="login" type="button">Se connecter</button>' in html
    assert "$('#login').classList.remove('hidden')" in html
    assert "$('#login').classList.toggle('hidden'" not in html


def test_expired_api_session_returns_to_login_screen():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "if(response.status===401){token=null;showAuth(" in html
    assert "Votre session a expiré ou n’est plus valide." in html


def test_login_handler_reports_missing_oidc_module():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "if(!auth||typeof auth.login!=='function')" in html
    assert "Module OIDC indisponible" in html
