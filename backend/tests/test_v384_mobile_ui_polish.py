from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_mobile_workspace_uses_fixed_safe_area_bottom_navigation():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert 'aria-label="Navigation principale"' in html
    assert 'class="nav-icon"' in html
    assert "position:fixed;z-index:50;left:0;right:0;bottom:0" in html
    assert "env(safe-area-inset-bottom)" in html
    for label in ("Assistant juridique", "Accueil", "Documents", "Collectivités", "Membres", "Abonnement"):
        assert f"<span>{label}</span>" in html


def test_privacy_notice_is_collapsed_until_user_opens_it():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert '<details class="notice notice-details">' in html
    assert "<summary>" in html
    assert "En savoir plus" in html
    assert "Google Gemini" in html


def test_legal_sources_are_individually_disclosable_without_html_injection():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "document.createElement('details')" in html
    assert "card.className='juris-source'" in html
    assert "excerpt.textContent=src.excerpt" in html
    assert "name.textContent=src.title||'Source juridique'" in html


def test_legal_source_links_remain_restricted_to_official_legifrance_https_hosts():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "u.protocol==='https:'" in html
    assert "['www.legifrance.gouv.fr','legifrance.gouv.fr'].includes(u.hostname)" in html
    assert "a.rel='noopener noreferrer'" in html


def test_visual_polish_does_not_change_oidc_or_chat_api_contracts():
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    auth = (ROOT / "frontend/oidc-auth.js").read_text(encoding="utf-8")
    assert "auth.login()" in html
    assert "window.CFDT_JURIS_OIDC" in auth
    assert "api('/api/v1/chat/ask'" in html
    assert "verification_status" in html
