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

def test_oidc_provider_errors_are_state_checked_and_cleaned_from_the_url():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    assert "const providerError = params.get('error');" in auth
    assert "state !== expected" in auth
    assert "sessionStorage.removeItem('cfdt_oidc_state');" in auth
    assert "history.replaceState({}, document.title, window.location.pathname + window.location.hash);" in auth
    assert "error_description" in auth and ".slice(0, 300)" in auth
