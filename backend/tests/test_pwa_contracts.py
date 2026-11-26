import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_pwa_manifest_is_root_scoped_and_uses_the_glacier_brand():
    manifest = json.loads((ROOT / "frontend/manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["id"] == manifest["start_url"] == manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["lang"] == "fr-FR"
    assert manifest["theme_color"] == "#eaf5fc"
    for icon in manifest["icons"]:
        assert icon["src"].startswith("/static/")
        assert (ROOT / "frontend" / icon["src"].removeprefix("/static/")).is_file()


def test_service_worker_only_caches_static_offline_shell():
    worker = (ROOT / "frontend/sw.js").read_text(encoding="utf-8")
    assert "const CACHE_NAME = 'dikevia-shell-v1'" in worker
    assert "OFFLINE_URL = '/static/offline.html'" in worker
    assert "request.method !== 'GET'" in worker
    assert "url.origin !== self.location.origin" in worker
    assert "request.mode !== 'navigate'" in worker
    assert "Authorization" not in worker
    assert "cache.put(" not in worker
    assert "/api/" not in worker


def test_service_worker_is_served_from_origin_root_without_stale_caching():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    assert '@app.get("/sw.js", include_in_schema=False)' in main
    assert 'FileResponse(FRONTEND / "sw.js"' in main
    assert '"Cache-Control": "no-cache"' in main


def test_frontend_registers_pwa_only_in_secure_context():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert '<link rel="manifest" href="/static/manifest.webmanifest">' in html
    assert "navigator.serviceWorker.register('/sw.js', {scope:'/'}" in html
    assert "window.isSecureContext" in html


def test_offline_fallback_does_not_persist_private_state():
    worker = (ROOT / "frontend/sw.js").read_text(encoding="utf-8")
    offline = (ROOT / "frontend/offline.html").read_text(encoding="utf-8")
    assert "localStorage" not in worker + offline
    assert "indexedDB" not in worker + offline
    assert "ne conserve pas les dossiers juridiques ni les conversations" in offline
