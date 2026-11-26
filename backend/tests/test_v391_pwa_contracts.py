import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pwa_manifest_is_root_scoped_and_has_a_valid_static_icon():
    manifest = json.loads((ROOT / "frontend/manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["id"] == manifest["start_url"] == manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["lang"] == "fr-FR"
    for icon in manifest["icons"]:
        assert icon["src"].startswith("/static/")
        assert (ROOT / "frontend" / icon["src"].removeprefix("/static/")).is_file()


def test_service_worker_only_caches_the_offline_shell_not_user_data():
    worker = (ROOT / "frontend/sw.js").read_text(encoding="utf-8")
    assert "const CACHE_NAME = 'dikevia-shell-v1'" in worker
    assert "OFFLINE_URL = '/static/offline.html'" in worker
    assert "cache.addAll([" in worker
    assert "'/static/dikevia-icon.svg'" in worker
    assert "'/static/manifest.webmanifest'" in worker
    assert "request.method !== 'GET'" in worker
    assert "url.origin !== self.location.origin" in worker
    assert "request.mode !== 'navigate'" in worker
    assert "No API, authentication, billing, documents, or user content is cached." in worker
    assert "/api/" not in worker


def test_service_worker_is_served_from_origin_root_without_stale_caching():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert '@app.get("/sw.js", include_in_schema=False)' in main
    assert 'FileResponse(' in main
    assert 'FRONTEND / "sw.js"' in main
    assert '"Cache-Control": "no-cache"' in main


def test_frontend_registers_pwa_only_in_secure_context():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert '<link rel="manifest" href="/static/manifest.webmanifest">' in html
    assert "navigator.serviceWorker.register('/sw.js', {scope:'/'}" in html
    assert "window.isSecureContext" in html


def test_android_shell_disables_backup_cleartext_and_ssl_error_bypass():
    manifest = (ROOT / "android/app/src/main/AndroidManifest.xml").read_text(encoding="utf-8")
    activity = (ROOT / "android/app/src/main/java/fr/dikevia/commercial/MainActivity.kt").read_text(encoding="utf-8")
    assert 'android:allowBackup="false"' in manifest
    assert 'android:usesCleartextTraffic="false"' in manifest
    assert "handler.cancel()" in activity
    assert "handler.proceed()" not in activity
    assert "addJavascriptInterface" not in activity


def test_offline_fallback_is_static_and_never_persists_private_state():
    worker = (ROOT / "frontend/sw.js").read_text(encoding="utf-8")
    offline = (ROOT / "frontend/offline.html").read_text(encoding="utf-8")
    assert "localStorage" not in worker
    assert "indexedDB" not in worker
    assert "cache.put(" not in worker
    assert "Authorization" not in worker
    assert "ne conserve pas les dossiers juridiques ni les conversations" in offline
    assert "localStorage" not in offline
    assert "indexedDB" not in offline
