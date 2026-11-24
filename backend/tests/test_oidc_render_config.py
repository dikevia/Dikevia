from pathlib import Path


def test_commercial_blueprint_pins_public_oidc_client_id():
    render = (Path(__file__).resolve().parents[2] / "render.yaml").read_text()
    assert '      - key: OIDC_CLIENT_ID\n        value: cfdt-juris-web' in render
