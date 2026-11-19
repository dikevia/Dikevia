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
    assert "cleanAuthCallbackUrl();" in auth
    assert "error_description" in auth and ".slice(0, 300)" in auth

def test_invitation_bearer_token_is_removed_from_the_url_immediately():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    store = auth.index("sessionStorage.setItem('cfdt_pending_invitation', initialInvitation);")
    cleanup = auth.index("cleanUrl.searchParams.delete('invitation_token');", store)
    assert store < cleanup
    assert "history.replaceState({}, document.title, cleanUrl.pathname + cleanUrl.search + cleanUrl.hash);" in auth

def test_oidc_callback_credentials_are_removed_before_network_exchange():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    callback = auth.index("async function completeCallback()")
    cleanup = auth.index("cleanAuthCallbackUrl();", callback)
    exchange = auth.index("fetch(oidc.token_endpoint", callback)
    assert cleanup < exchange
    assert "for (const key of ['code', 'state', 'error', 'error_description', 'iss', 'session_state'])" in auth
    assert "cleanUrl.searchParams.delete(key);" in auth

def test_logout_clears_pending_invitation_and_oidc_transient_state():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    logout = auth[auth.index("async logout()"):]
    assert "accessToken=null;expiresAt=0;" in logout
    assert "sessionStorage.removeItem('cfdt_oidc_state');" in logout
    assert "sessionStorage.removeItem('cfdt_oidc_verifier');" in logout
    assert "sessionStorage.removeItem('cfdt_pending_invitation');" in logout
