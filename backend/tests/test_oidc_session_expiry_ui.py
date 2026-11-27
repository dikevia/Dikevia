from pathlib import Path


def test_login_action_stays_visible_and_explains_a_missing_oidc_module():
    html = (Path(__file__).resolve().parents[2] / "frontend/index.html").read_text(encoding="utf-8")
    assert '<button id="login" type="button">Se connecter</button>' in html
    assert "$('#login').classList.remove('hidden')" in html
    assert "const client = window.CFDT_JURIS_AUTH;" in html
    assert "typeof client.login !== 'function'" in html
    assert "configuration OIDC navigateur non chargée" in html


def test_api_unauthorized_response_returns_user_to_login_screen():
    html = (Path(__file__).resolve().parents[2] / "frontend/index.html").read_text(encoding="utf-8")
    assert "if(response.status===401){token=null;showAuth(" in html
    assert "Votre session a expiré ou n’est plus valide." in html
