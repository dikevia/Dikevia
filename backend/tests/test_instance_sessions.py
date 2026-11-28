from datetime import date
from pathlib import Path

import pytest

from app.instance_sessions import validate_instance_session, render_instance_session_pdf

ROOT = Path(__file__).parents[2]


@pytest.mark.parametrize("instance", ["CST", "CAP", "CCP", "F3SCT"])
def test_instance_session_accepts_all_four_instances(instance):
    payload = validate_instance_session({
        "instance_code": instance,
        "title": "Séance de préparation",
        "meeting_date": "2026-12-15",
        "agenda": [{"title": "Point 1", "description": "Examen du dossier"}],
        "preparation": {"legal_research_status": "A_VERIFIER"},
        "questions": ["Quelle est la compétence de l'instance ?"],
        "documents": [{"name": "Convocation", "status": "A_DEMANDER"}],
        "minutes": "Compte rendu provisoire.",
        "action_items": [{"task": "Transmettre les pièces", "owner": "Secrétariat"}],
    })
    assert payload["instance_code"] == instance
    assert payload["meeting_date"] == "2026-12-15"
    assert payload["agenda"][0]["title"] == "Point 1"


def test_instance_session_rejects_unknown_fields_and_invalid_values():
    base = {"instance_code": "CST", "title": "Séance CST"}
    with pytest.raises(ValueError):
        validate_instance_session({**base, "is_approved_by_ai": True})
    with pytest.raises(ValueError):
        validate_instance_session({**base, "instance_code": "JURIS"})
    with pytest.raises(ValueError):
        validate_instance_session({**base, "meeting_status": "APPROVED_BY_AI"})
    with pytest.raises(ValueError):
        validate_instance_session({**base, "minutes": "x" * 50001})
    with pytest.raises(ValueError):
        validate_instance_session({**base, "meeting_date": "15/12/2026"})


def test_instance_session_migration_enforces_tenant_rls_and_rollback():
    migration = (ROOT / "database/migrations/035_instance_sessions.sql").read_text()
    assert "ALTER TABLE instance_sessions ENABLE ROW LEVEL SECURITY" in migration
    assert "ALTER TABLE instance_sessions FORCE ROW LEVEL SECURITY" in migration
    assert "app.current_org_id" in migration
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON instance_sessions TO cfdt_juris_app" in migration
    assert (ROOT / "database/migrations/rollback/035_instance_sessions.down.sql").exists()


def test_instance_session_frontend_exposes_shared_session_dossier_workflow():
    html = (ROOT / "frontend/index.html").read_text()
    for control in (
        "instanceSessionsPanel", "refreshInstanceSessions", "sessionTitle",
        "sessionAgenda", "sessionQuestions", "sessionDocuments", "sessionMinutes",
        "sessionActions", "createInstanceSession", "saveInstanceSession", "exportInstanceSessionPdf", "continueSessionWithJuris",
        "/api/v1/instances/sessions",
    ):
        assert control in html
    assert "loadInstanceSessions()" in html
    assert "split(/\\r?\\n/)" in html
    assert ".join('\\n')" in html
    assert "preparation:activeInstanceSession?activeInstanceSession.preparation:(latestInstancePreparation||{})" in html
    assert "/pdf" in html
    assert "MISSION JURIS" in html
    assert "N’invente aucune source" in html



def test_instance_session_pdf_displays_linked_document_metadata():
    from io import BytesIO
    from pypdf import PdfReader

    pdf = render_instance_session_pdf({
        "id": "test-linked-doc",
        "instance_code": "CST",
        "title": "Séance CST — documents liés",
        "meeting_status": "PREPARATION",
        "documents": [{
            "document_id": "doc-123", "title": "Délibération temps de travail",
            "collectivity_name": "Ville de test", "validation_status": "VERIFIED",
            "scan_status": "CLEAN",
        }],
    })
    text = " ".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
    assert "Délibération temps de travail" in text
    assert "Ville de test" in text
    assert "VERIFIED" in text
    assert "CLEAN" in text
    assert "doc-123" in text


def test_instance_session_pdf_contains_agenda_notes_and_warning():
    from pypdf import PdfReader
    from io import BytesIO

    pdf = render_instance_session_pdf({
        "id": "test",
        "instance_code": "F3SCT",
        "title": "Séance F3SCT décembre",
        "meeting_date": "2026-12-15",
        "meeting_status": "TENUE",
        "agenda": ["DUERP et programme annuel"],
        "preparation": {"legal_research_status": "A_VERIFIER"},
        "questions": ["Quelles mesures de prévention sont prévues ?"],
        "documents": ["DUERP actualisé"],
        "minutes": "Les représentants demandent un calendrier.",
        "action_items": ["Transmettre le plan de prévention"],
    })
    assert pdf.startswith(b"%PDF-")
    extracted = "\\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
    assert "DUERP et programme annuel" in extracted
    assert "Quelles mesures de prévention" in extracted
    assert "calendrier" in extracted
    assert "ne constituent pas une validation juridique" in " ".join(extracted.split())


def test_instance_session_api_has_list_create_read_and_update_routes():
    from app.main import app

    routes = {
        (route.path, method)
        for route in app.routes if hasattr(route, "methods")
        for method in route.methods
    }
    assert ("/api/v1/instances/sessions", "GET") in routes
    assert ("/api/v1/instances/sessions", "POST") in routes
    assert ("/api/v1/instances/sessions/{session_id}", "GET") in routes
    assert ("/api/v1/instances/sessions/{session_id}", "PUT") in routes
    assert ("/api/v1/instances/sessions/{session_id}/pdf", "GET") in routes


def test_session_document_reference_validation_is_tenant_scoped_and_server_resolved():
    from app.main import validate_instance_session_document_refs
    import inspect

    source = inspect.getsource(validate_instance_session_document_refs)
    assert "d.organization_id=$1::uuid" in source
    assert "d.id=ANY($2::uuid[])" in source
    assert '"scan_status": row["scan_status"]' in source
    assert '"validation_status": row["validation_status"]' in source


def test_instance_session_instance_identity_is_immutable_on_update():
    from app.instance_sessions import ensure_instance_identity_unchanged

    ensure_instance_identity_unchanged("CST", {"title": "Nouvel intitulé"})
    ensure_instance_identity_unchanged("F3SCT", {"instance_code": "F3SCT"})
    with pytest.raises(ValueError, match="ne peut pas être modifiée"):
        ensure_instance_identity_unchanged("CST", {"instance_code": "CAP"})


def test_loaded_instance_session_cannot_be_reassigned_to_another_instance_in_ui():
    html = (ROOT / "frontend/index.html").read_text()
    assert "$('#instanceType').disabled=true" in html
    assert "$('#instanceType').disabled=false" in html
    assert "if(activeInstanceSession){sessionMessage('Ce dossier est rattaché à '" in html
