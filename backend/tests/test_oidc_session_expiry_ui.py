from pathlib import Path


def test_api_unauthorized_response_returns_user_to_login_screen():
    html = (Path(__file__).resolve().parents[2] / "frontend/index.html").read_text(encoding="utf-8")
    assert "if(response.status===401){token=null;showAuth(" in html
    assert "Votre session a expiré ou n’est plus valide." in html
