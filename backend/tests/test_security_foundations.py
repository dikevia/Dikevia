from pathlib import Path
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import AskRequest
from app.orchestrator import LegalOrchestrator

client = TestClient(app)

def test_health_is_public():
    assert client.get("/health").json() == {"status": "ok"}

def test_chat_rejects_anonymous_user():
    response = client.post("/api/v1/chat/ask", json={
        "employer": "VILLE_SAINT_ETIENNE", "question": "Quelle règle s'applique ici ?"
    })
    assert response.status_code == 401

def test_chat_never_fabricates_without_sources():
    import asyncio
    response = asyncio.run(LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", question="Quelle règle s'applique ici ?"),
        "00000000-0000-0000-0000-000000000001"))
    assert response.verification_status == "PARTIELLEMENT_VERIFIE"
    assert response.sources
    assert any("Légifrance" in item for item in response.missing_information)

def test_every_private_table_is_in_rls_migration():
    sql = (Path(__file__).parents[2] / "database/migrations/001_initial_multi_tenant.sql").read_text()
    private_tables = ["organizations","memberships","collectivities","documents","document_versions",
        "document_relations","invitations","organization_settings","subscriptions","audit_events"]
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    for table in private_tables:
        assert f"'{table}'" in sql
    assert "NULLIF(current_setting('app.current_org_id',true),'')::uuid" in sql
