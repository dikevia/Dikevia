from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "import_public_guidance_sources",
    ROOT / "scripts" / "import_public_guidance_sources.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MODULE)


def test_public_guidance_importer_rejects_unregistered_hosts():
    source = {"domains": ["www.fonction-publique.gouv.fr"]}
    MODULE.validate_public_url(
        "https://www.fonction-publique.gouv.fr/guide.pdf", source
    )
    try:
        MODULE.validate_public_url("https://evil.example/guide.pdf", source)
    except ValueError as exc:
        assert "hors liste" in str(exc)
    else:
        raise AssertionError("Un hôte absent du registre ne doit pas être téléchargé.")


def test_html_extraction_ignores_navigation_and_scripts():
    html = (
        "<html><head><title>Guide statutaire</title></head><body>"
        "<nav>Navigation parasite</nav><script>secret()</script>"
        "<main><h1>Guide</h1><p>" + ("Règle administrative utile. " * 35)
        + "</p></main><footer>Pied de page</footer></body></html>"
    )
    text, details = MODULE.extract_html(html.encode())
    assert "Navigation parasite" not in text
    assert "secret()" not in text
    assert "Pied de page" not in text
    assert details["html_title"] == "Guide statutaire"
    assert len(text) >= 500


def test_pdf_extraction_records_pages_and_rejects_empty_pdf():
    from io import BytesIO
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=300, height=300)
    buffer = BytesIO()
    writer.write(buffer)
    try:
        MODULE.extract_pdf(buffer.getvalue())
    except ValueError as exc:
        assert "sans couche texte" in str(exc)
    else:
        raise AssertionError("Un PDF image sans OCR ne doit pas être indexé comme texte.")



def test_guidance_seed_scope_must_include_fpt_or_common_public_service():
    assert MODULE.seed_is_fpt_relevant({"scope": ["FPT"]}) is True
    assert MODULE.seed_is_fpt_relevant({"scope": ["FPE", "FPT", "FPH"]}) is True
    assert MODULE.seed_is_fpt_relevant({"scope": ["COMMON_PUBLIC_SERVICE"]}) is True
    assert MODULE.seed_is_fpt_relevant({"scope": ["FPE"]}) is False
    assert MODULE.seed_is_fpt_relevant({"scope": ["TRANSVERSAL"]}) is False
    assert MODULE.seed_is_fpt_relevant({"scope": []}) is False


def test_guidance_seed_download_requires_both_source_and_document_reuse_approval():
    source_approved = {"status": "REUSE_APPROVED"}
    source_pending = {"status": "REVIEW_REQUIRED"}
    seed_approved = {"reuse_status": "REUSE_APPROVED"}
    seed_pending = {"reuse_status": "REVIEW_REQUIRED"}
    assert MODULE.seed_reuse_is_approved(seed_approved, source_approved) is True
    assert MODULE.seed_reuse_is_approved(seed_pending, source_approved) is False
    assert MODULE.seed_reuse_is_approved(seed_approved, source_pending) is False
