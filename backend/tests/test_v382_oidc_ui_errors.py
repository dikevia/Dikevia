from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_oidc_login_and_logout_errors_are_shown_in_the_ui():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "Connexion impossible :" in html
    assert "Déconnexion locale effectuée." in html
    assert '<button id="logout" class="secondary" type="button" aria-label="Se déconnecter de Dikévia">Déconnexion</button>' in html
    assert "}).finally(() => { button.disabled = false; });" in html

def test_juris_visual_identity_and_shared_instance_entry_points_are_present():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    theme = (ROOT / "frontend/dikevia-chat-theme.css").read_text(encoding="utf-8")

    assert '<strong>JURIS</strong>' in html
    assert 'class="juris-orb"' in html
    assert 'class="juris-orb juris-orb-large"' in html
    for instance in ("CST", "CAP", "CCP", "FS"):
        assert f'data-instance-choice="{instance}"' in html
    assert 'id="continueInstanceWithJuris"' in html
    assert "setView('ask')" in html
    assert ".instance-launch-grid" in theme
    assert "@keyframes juris-orb-breathe" in theme
    assert ".instance-juris-bridge" in theme
