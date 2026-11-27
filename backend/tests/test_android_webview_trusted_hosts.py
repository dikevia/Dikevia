from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[2]


def test_android_webview_trusts_only_active_staging_and_auth0_hosts():
    activity = (
        ROOT / "android/app/src/main/java/fr/dikevia/commercial/MainActivity.kt"
    ).read_text(encoding="utf-8")
    match = re.search(
        r"private val TRUSTED_HOSTS = setOf\((.*?)\n        \)",
        activity,
        flags=re.DOTALL,
    )
    assert match is not None

    hosts = re.findall(r'"([^"]+)"', match.group(1))
    assert hosts == [
        "dikevia-vector-beta-staging.onrender.com",
        "dev-brlgaz1yh2de3mjo.us.auth0.com",
    ]
    assert "dikevia-commercial-api-l2r8.onrender.com" not in hosts
    assert "dikevia-identity-l2r8.onrender.com" not in hosts
    assert not any("keycloak" in host.casefold() for host in hosts)
