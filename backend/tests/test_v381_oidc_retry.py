from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_oidc_login_can_be_retried_after_callback_failure():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    assert "const ready=restoreSsoSession();" in auth
    assert "async getAccessToken()" in auth
    assert "await ready;" in auth
    assert "async login(){await ready.catch(()=>{});return login();}" in auth
    assert "async logout()" in auth


def test_oidc_restores_existing_keycloak_session_without_persisting_tokens():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    assert "authorizationUrl(oidc,redirectUri,state,verifier,'none',nonce)" in auth
    assert "silentCheckSso()" in auth
    assert "frame.src=authUrl;" in auth
    assert "code_challenge_method:'S256'" in auth
    assert "code_verifier:verifier" in auth
    assert "localStorage" not in auth
    assert "refresh_token" not in auth
    assert "sessionStorage.setItem('cfdt_oidc_access_token'" not in auth


def test_oidc_silent_callback_does_not_loop_when_no_sso_session_exists():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    callback = (ROOT / "frontend/silent-check-sso.html").read_text(encoding="utf-8")
    assert "const hadCallback=" in auth
    assert "if(hadCallback||completed||accessToken)return;" in auth
    assert "cfdt-oidc-silent-callback" in auth
    assert "cfdt-oidc-silent-callback" in callback
    assert "event.origin!==window.location.origin" in auth
    assert "event.source!==frame.contentWindow" in auth


def test_oidc_silent_failure_does_not_repeat_until_user_retries():
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    assert "if(sessionStorage.getItem('cfdt_oidc_silent_failed')==='1')return;" in auth
    assert "sessionStorage.removeItem('cfdt_oidc_silent_failed');" in auth
    assert "setTimeout(()=>finish(null),8000)" in auth


def test_android_webview_flushes_oidc_cookies_without_clearing_the_session():
    activity = (
        ROOT / "android/app/src/main/java/fr/dikevia/commercial/MainActivity.kt"
    ).read_text(encoding="utf-8")
    assert "override fun onPause()" in activity
    assert "CookieManager.getInstance().flush()" in activity
    assert "removeAllCookies" not in activity
    assert "removeSessionCookies" not in activity
