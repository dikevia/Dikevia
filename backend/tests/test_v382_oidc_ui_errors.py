from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_oidc_login_and_logout_errors_are_shown_in_the_ui():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "Connexion impossible :" in html
    assert "Déconnexion locale effectuée." in html
    assert '<button id="logout" class="secondary" type="button" aria-label="Se déconnecter de Dikévia">Déconnexion</button>' in html
    assert "finally{button.disabled=false;}" in html
