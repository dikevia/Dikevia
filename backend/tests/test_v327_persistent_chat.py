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

def test_conversation_history_supports_ten_exchange_context_and_resolves_followup_chains():
    from app.legal_qualification import (
        CONVERSATION_HISTORY_MESSAGE_LIMIT,
        RECENT_USER_CONTEXT_LIMIT,
        build_contextual_research_question,
    )

    assert CONVERSATION_HISTORY_MESSAGE_LIMIT == 20
    assert RECENT_USER_CONTEXT_LIMIT == 10

    prior = [
        "Je suis fonctionnaire territorial et je subis un accident de service.",
        "Et pour les contractuels ?",
    ]
    resolved = build_contextual_research_question("Et pour les stagiaires ?", prior)
    assert resolved.startswith("Et pour les stagiaires ?")
    assert "accident de service" in resolved
    assert build_contextual_research_question(
        "Comment fonctionne le CET ?", prior
    ) == "Comment fonctionne le CET ?"

def test_chat_route_loads_twenty_messages_and_ai_planner_keeps_ten_user_turns():
    main = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    orchestrator = (ROOT / "backend/app/orchestrator.py").read_text(encoding="utf-8")
    provider = (ROOT / "backend/app/ai_provider.py").read_text(encoding="utf-8")
    assert "ORDER BY created_at DESC,id DESC LIMIT $3" in main
    assert "CONVERSATION_HISTORY_MESSAGE_LIMIT" in main
    assert "[-CONVERSATION_HISTORY_MESSAGE_LIMIT:]" in orchestrator
    assert "[-RECENT_USER_CONTEXT_LIMIT:]" in provider


def test_short_answer_uses_previous_assistant_clarification_without_losing_legal_topic():
    from app.legal_qualification import build_contextual_research_question

    prior_users = ["Je suis en CITIS après un accident de service."]
    prior_assistant = ["Pour préciser votre situation, êtes-vous titulaire ou contractuel ?"]
    resolved = build_contextual_research_question(
        "Contractuel", prior_users, prior_assistant
    )
    assert resolved.startswith("Contractuel")
    assert "CITIS" in resolved
    assert "titulaire ou contractuel" in resolved

    assert build_contextual_research_question(
        "Comment fonctionne le CET ?", prior_users, prior_assistant
    ) == "Comment fonctionne le CET ?"


def test_short_answer_does_not_inherit_topic_when_assistant_did_not_ask_a_question():
    from app.legal_qualification import build_contextual_research_question

    resolved = build_contextual_research_question(
        "Contractuel",
        ["Je suis en CITIS après un accident de service."],
        ["Voici les règles applicables au CITIS."],
    )
    assert resolved == "Contractuel"
