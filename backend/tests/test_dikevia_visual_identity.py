from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_standard_app_uses_light_blue_identity_and_fullscreen_chat():
    css = (ROOT / "frontend/dikevia-chat-theme.css").read_text(encoding="utf-8")
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")
    assert "Dikévia light identity" in css
    assert "--dk-blue:#527eaf" in css
    assert "background:#f7f9fc" in css
    assert 'href="/static/dikevia-chat-theme.css"' in html
    assert "@media (min-width: 761px)" in css
    assert "Final chat workspace layout" in css


def test_standard_android_launcher_matches_light_blue_identity():
    foreground = (ROOT / "android/app/src/standard/res/drawable/dikevia_icon_foreground.xml").read_text(encoding="utf-8")
    legacy = (ROOT / "android/app/src/standard/res/mipmap/ic_launcher.xml").read_text(encoding="utf-8")
    colors = (ROOT / "android/app/src/standard/res/values/icon_colors.xml").read_text(encoding="utf-8")
    assert "#18324F" in foreground and "#527EAF" in foreground
    assert "#EDF3FA" in legacy
    assert "#EDF3FA" in colors
    assert "#00483D" not in legacy
    assert "#D9A441" not in foreground
