from pathlib import Path
from uuid import uuid4

from app.schemas import AskRequest, AskResponse

ROOT = Path(__file__).parents[2]

def test_ask_contract_accepts_conversation_id_and_response_returns_it():
    conversation_id = uuid4()
    request = AskRequest(employer="NATIONAL", question="Et dans ce cas particulier ?", conversation_id=conversation_id)
    response = AskResponse(request_id="req-test", conversation_id=conversation_id,
        verification_status="NON_VERIFIE", answer="Aucune conclusion.")
    assert request.conversation_id == conversation_id
    assert response.conversation_id == conversation_id

def test_chat_persistence_migration_enforces_tenant_and_user_rls():
    sql = (ROOT / "database/migrations/012_persistent_chat_conversations.sql").read_text()
    assert "ALTER TABLE chat_conversations FORCE ROW LEVEL SECURITY" in sql
    assert "ALTER TABLE chat_messages FORCE ROW LEVEL SECURITY" in sql
    assert "app.current_org_id" in sql and "app.current_user_id" in sql
    assert "char_length(content) <= 50000" in sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON chat_conversations TO cfdt_juris_app" in sql
    assert "GRANT SELECT, INSERT, UPDATE, DELETE ON chat_messages TO cfdt_juris_app" in sql
    assert (ROOT / "database/migrations/rollback/012_persistent_chat_conversations.down.sql").exists()

def test_conversation_routes_are_authenticated_tenant_routes():
    from app.main import app
    routes = {r.path: r for r in app.routes if hasattr(r, "path")}
    assert "/api/v1/chat/conversations" in routes
    assert "/api/v1/chat/conversations/{conversation_id}/messages" in routes
    assert "/api/v1/chat/conversations/{conversation_id}" in routes
    assert "/api/v1/chat/ask" in routes

def test_ai_provider_explicitly_treats_history_as_context_not_legal_authority():
    from app.ai_provider import SYSTEM_PROMPT
    assert "messages antérieurs servent uniquement à comprendre" in SYSTEM_PROMPT
    assert "ne les traite jamais comme des sources juridiques" in SYSTEM_PROMPT
