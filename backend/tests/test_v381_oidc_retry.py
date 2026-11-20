from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_oidc_login_can_be_retried_after_callback_failure():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    # The callback promise is shared with token retrieval, so its failure must
    # remain visible to the application while not permanently blocking login.
    assert "const ready = restoreSsoSession();" in auth
    assert "async getAccessToken() { await ready;" in auth
    assert "async login() { await ready.catch(() => {}); return login(); }" in auth
    assert "async logout()" in auth


def test_oidc_restores_existing_keycloak_session_without_persisting_tokens():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    assert "await beginAuthorization('none');" in auth
    assert "params.prompt = prompt" in auth
    assert "cfdt_oidc_silent_attempt" in auth
    assert "login_required" in auth
    assert "localStorage" not in auth
    assert "sessionStorage.setItem('cfdt_oidc_access_token'" not in auth


def test_oidc_silent_callback_does_not_loop_when_no_sso_session_exists():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    assert "const hadCallback =" in auth
    assert "if (hadCallback || completed || accessToken) return;" in auth
    assert "flow === 'silent'" in auth
