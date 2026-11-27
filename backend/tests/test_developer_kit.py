from pathlib import Path

from scripts.package_developer_kit import include_file


ROOT = Path(__file__).resolve().parents[2]


def test_developer_kit_contains_only_current_source_of_truth_paths():
    assert include_file(ROOT / "backend/app/main.py")
    assert include_file(ROOT / "frontend/index.html")
    assert include_file(ROOT / "docs/57_ETAT_CONSOLIDE_2026-11-27.md")
    assert include_file(ROOT / "render.yaml")


def test_developer_kit_excludes_legacy_root_level_duplicates_and_old_compose():
    for path in (
        "main.py",
        "index.html",
        "ai_provider.py",
        "docker-compose.yml",
        "docker-compose.proxy.yml",
        "01_PRODUCT_REQUIREMENTS.md",
        "02_ARCHITECTURE.md",
    ):
        assert not include_file(ROOT / path), path
