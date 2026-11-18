from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_oidc_login_can_be_retried_after_callback_failure():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    # The callback promise is shared with token retrieval, so its failure must
    # remain visible to the application while not permanently blocking login.
    assert "const ready = completeCallback();" in auth
    assert "async getAccessToken() { await ready;" in auth
    assert "async login() { await ready.catch(() => {}); return login(); }" in auth
    assert "async logout()" in auth
