from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_standard_app_uses_jarvis_glacier_identity_and_animated_orb():
    css = (ROOT / "frontend/dikevia-chat-theme.css").read_text(encoding="utf-8")
    html = (ROOT / "frontend/index.html").read_text(encoding="utf-8")

    assert 'href="/static/dikevia-chat-theme.css"' in html
    assert "DIKEVIA JARVIS — palette verrouillée : glacier / acier / bleu nuit." in css
    jarvis = css.split("DIKEVIA JARVIS — palette verrouillée", 1)[1]
    assert "--dk-bg:#f3f7fb!important" in jarvis
    assert "--dk-ink:#17283b!important" in jarvis
    assert "--dk-emerald:#287fbd!important" in jarvis
    assert ".juris-welcome-icon" in jarvis
    assert "animation:jarvis-core-pulse 3.8s ease-in-out infinite!important" in jarvis
    assert "@keyframes jarvis-core-pulse" in jarvis
    assert "prefers-reduced-motion:reduce" in jarvis


def test_jarvis_visual_state_styles_are_defined_for_assistant_activity():
    css = (ROOT / "frontend/dikevia-chat-theme.css").read_text(encoding="utf-8")
    assert ".juris-message.assistant.is-generating .juris-avatar:before" in css
    assert ".juris-message.assistant .juris-avatar.is-speaking:before" in css
    assert "@keyframes dikevia-speaking" in css


def test_standard_android_launcher_matches_jarvis_blue_identity():
    foreground = (ROOT / "android/app/src/standard/res/drawable/dikevia_icon_foreground.xml").read_text(encoding="utf-8")
    legacy = (ROOT / "android/app/src/standard/res/mipmap/ic_launcher.xml").read_text(encoding="utf-8")
    colors = (ROOT / "android/app/src/standard/res/values/icon_colors.xml").read_text(encoding="utf-8")

    assert "#18324F" in foreground and "#527EAF" in foreground
    assert "#EDF3FA" in legacy
    assert "#EDF3FA" in colors
    assert "#00483D" not in legacy
    assert "#D9A441" not in foreground


def test_admin_android_launcher_uses_same_jarvis_blue_family():
    foreground = (ROOT / "android/app/src/admin/res/drawable/dikevia_icon_foreground.xml").read_text(encoding="utf-8")
    legacy = (ROOT / "android/app/src/admin/res/mipmap/ic_launcher.xml").read_text(encoding="utf-8")
    colors = (ROOT / "android/app/src/admin/res/values/icon_colors.xml").read_text(encoding="utf-8")

    assert "#18324F" in foreground
    assert "#527EAF" in foreground
    assert "#EAF5FC" in legacy
    assert "#18324F" in colors
