from datetime import date
from pathlib import Path

import pytest

from app.instance_sessions import validate_instance_session

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
