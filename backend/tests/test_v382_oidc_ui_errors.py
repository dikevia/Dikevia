from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_oidc_login_and_logout_errors_are_shown_in_the_ui():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "Connexion impossible :" in html
    assert "Déconnexion locale effectuée." in html
    assert "finally{button.disabled=false;}" in html

def test_oidc_login_button_remains_visible_and_uses_the_docker_generated_config():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert '<button id="login">Se connecter</button>' in html
    assert '<script src="/static/auth-config.js"></script>' in html
    assert '/static/auth-config.render.js' not in html
