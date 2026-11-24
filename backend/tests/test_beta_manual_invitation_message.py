from pathlib import Path


def test_manual_invitation_explains_keycloak_account_prerequisite():
    html = (Path(__file__).resolve().parents[2] / "frontend/index.html").read_text()
    assert "L’auto-inscription Keycloak est désactivée" in html
    assert "un administrateur doit créer et vérifier le compte" in html
    assert "Transmettez ensuite ce jeton par un canal sûr" in html
