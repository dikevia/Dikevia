from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = spec_from_file_location("package_developer_kit", ROOT / "scripts" / "package_developer_kit.py")
MODULE = module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)
include_file = MODULE.include_file


def test_developer_kit_contains_only_current_source_of_truth_paths():
    assert include_file(ROOT / "backend/app/main.py")
    assert include_file(ROOT / "frontend/index.html")
    assert include_file(ROOT / "docs/57_ETAT_CONSOLIDE_2026-11-27.md")
    assert include_file(ROOT / "render.yaml")


def test_legacy_root_duplicates_are_archived_and_excluded_from_developer_kit():
    for path in (
        "main.py",
        "index.html",
        "ai_provider.py",
        "docker-compose.yml",
        "docker-compose.proxy.yml",
        "01_PRODUCT_REQUIREMENTS.md",
        "02_ARCHITECTURE.md",
    ):
        assert not (ROOT / path).exists(), path
        archived = ROOT / "archive" / "legacy-root" / path
        assert archived.is_file(), str(archived)
        assert not include_file(archived), str(archived)
