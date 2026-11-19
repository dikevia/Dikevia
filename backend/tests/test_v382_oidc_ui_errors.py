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


def test_oidc_config_is_generated_and_served_from_the_static_directory():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    app = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    config = ROOT / "frontend/auth-config.render.js"
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert config.is_file()
    assert "COPY frontend/auth-config.render.js /srv/frontend/auth-config.js" in dockerfile
    assert 'app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")' in app
    assert '<script src="/static/auth-config.js"></script>' in html
    assert "window.CFDT_JURIS_OIDC" in config.read_text(encoding="utf-8")

def test_auth_pages_do_not_leak_url_tokens_through_referrers():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert '<meta name="referrer" content="no-referrer">' in html
