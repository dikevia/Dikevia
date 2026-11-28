from pathlib import Path

import pytest

from app.dossiers import build_dossier_content, validate_dossier_content

ROOT = Path(__file__).parents[2]


def test_dossier_compiles_user_exchanges_assistant_answers_and_verified_sources_without_inventing_facts():
    content = build_dossier_content(
        {"title": "Congé annuel"},
        [
            {"role": "user", "content": "Mon employeur refuse mes congés du 3 au 10 juin.",
             "metadata": '{"employer":"NATIONAL","facts_date":"2026-06-03"}'},
            {"role": "assistant", "content": "Analyse à vérifier.", "metadata": {
                "verification_status": "PARTIELLEMENT_VERIFIE",
                "sources": [{"title": "CGFP article L. 621-1", "source_id": "LEGIARTI123", "official_url": "https://www.legifrance.gouv.fr"}],
                "missing_information": ["Vérifier la délibération locale."]}},
        ],
    )
    assert "Mon employeur refuse" in content["facts_summary"]
    assert content["legal_analyses"][0]["verification_status"] == "PARTIELLEMENT_VERIFIE"
    assert content["legal_sources"][0]["source_id"] == "LEGIARTI123"
    assert content["points_to_verify"] == ["Vérifier la délibération locale."]
    assert content["status"] == "BROUILLON_A_VALIDER"
    assert "ne vaut ni validation juridique" in content["warning"]


def test_dossier_content_validation_limits_fields_and_status():
    base = build_dossier_content({"title": "Test"}, [{"role": "user", "content": "Question"}])
    assert validate_dossier_content(base)["title"] == "Test"
    bad = dict(base, status="APPROUVE_PAR_IA")
    with pytest.raises(ValueError):
        validate_dossier_content(bad)
    bad = dict(base, facts_summary="x" * 20001)
    with pytest.raises(ValueError):
        validate_dossier_content(bad)


def test_dossier_migration_enforces_owner_and_tenant_rls_and_has_rollback():
    sql = (ROOT / "database/migrations/013_legal_dossiers.sql").read_text()
    assert "ALTER TABLE legal_dossiers FORCE ROW LEVEL SECURITY" in sql
    assert "app.current_org_id" in sql and "app.current_user_id" in sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON legal_dossiers TO cfdt_juris_app" in sql
    assert (ROOT / "database/migrations/rollback/013_legal_dossiers.down.sql").exists()


def test_dossier_routes_are_authenticated_tenant_routes():
    from app.main import app
    paths = {r.path for r in app.routes if hasattr(r, "path")}
    assert "/api/v1/chat/conversations/{conversation_id}/dossier" in paths
    update_route = next(r for r in app.routes if getattr(r, "path", None) == "/api/v1/chat/conversations/{conversation_id}/dossier" and "PUT" in getattr(r, "methods", set()))
    import inspect
    source = inspect.getsource(update_route.endpoint)
    assert '"legal_analyses"' not in source or "editable =" in source
    assert '"legal_sources"' not in source or "editable =" in source


def test_frontend_exposes_dossier_build_edit_save_and_print_actions():
    html = (ROOT / "frontend/index.html").read_text()
    for item in ("buildDossier", "saveDossier", "printDossier", "dossierFacts", "dossierSources"):
        assert item in html
    assert "localStorage" not in html



def test_dossier_persists_local_source_collectivity_and_validation_fields():
    main_source = (ROOT / "backend/app/main.py").read_text()
    html = (ROOT / "frontend/index.html").read_text()
    for field in ("collectivity", "local_document_type", "validation_status", "effective_from", "effective_to"):
        assert f'"{field}"' in main_source
    assert "x.collectivity" in html
    assert "x.local_document_type" in html
    assert "x.validation_status" in html



def test_server_pdf_export_renders_dossier_without_losing_legal_caveats():
    from pypdf import PdfReader
    from io import BytesIO
    from app.dossier_pdf import render_legal_dossier_pdf

    content = build_dossier_content(
        {"title": "Dossier congés"},
        [
            {"role": "user", "content": "Refus de congés les 3 et 4 juin."},
            {"role": "assistant", "content": "Analyse à contrôler.",
             "metadata": {"verification_status": "NON_VERIFIE",
                          "sources": [{"title": "CGFP L. 621-1",
                                       "official_url": "https://www.legifrance.gouv.fr"}]}},
        ],
    )
    pdf = render_legal_dossier_pdf(content, "test-dossier")
    assert pdf.startswith(b"%PDF-")
    reader = PdfReader(BytesIO(pdf))
    extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
    assert "Dossier congés" in extracted
    assert "NON_VERIFIE" in extracted
    assert "ne vaut ni validation juridique" in extracted
    assert "CGFP L. 621-1" in extracted


def test_dossier_pdf_route_is_authenticated_and_private():
    from app.main import app
    route = next(
        r for r in app.routes
        if getattr(r, "path", None) == "/api/v1/chat/conversations/{conversation_id}/dossier/pdf"
    )
    import inspect
    source = inspect.getsource(route.endpoint)
    assert "organization_id=$2::uuid AND user_id=$3::uuid" in source
    assert "application/pdf" in source
    assert "Cache-Control" in source
