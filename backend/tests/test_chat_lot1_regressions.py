import ast
import inspect

import pytest
from pydantic import ValidationError

from app.ai_provider import LegalResearchPlan
from app.legal_qualification import build_contextual_research_question
from app.schemas import AskRequest
from app.orchestrator import LegalOrchestrator
import app.orchestrator as orchestrator_module


@pytest.mark.parametrize("question", ["oui", "non", "CDI", "CDD"])
def test_chat_request_accepts_short_conversational_replies(question):
    request = AskRequest(employer="NATIONAL", question=question)
    assert request.question == question


@pytest.mark.parametrize("question", ["", "   "])
def test_chat_request_rejects_empty_or_whitespace_only_messages(question):
    with pytest.raises(ValidationError):
        AskRequest(employer="NATIONAL", question=question)


def test_short_reply_inherits_previous_clarification_context():
    resolved = build_contextual_research_question(
        "oui",
        ["Un agent titulaire peut-il demander une disponibilité ?"],
        ["Quel est votre statut : titulaire ou contractuel ?"],
    )
    assert "oui" in resolved.lower()
    assert "disponibilité" in resolved.lower()
    assert "titulaire ou contractuel" in resolved.lower()


@pytest.mark.asyncio
async def test_research_planner_clarification_is_returned_before_retrieval(monkeypatch):
    async def ask_plan(**kwargs):
        return LegalResearchPlan(
            queries=[],
            legal_issues=[],
            clarification_needed="Êtes-vous fonctionnaire titulaire ou agent contractuel ?",
        )

    async def forbidden_retrieval(*args, **kwargs):
        pytest.fail("Aucune recherche documentaire ne doit démarrer avant la clarification.")

    monkeypatch.setattr(orchestrator_module, "plan_legal_research", ask_plan)
    monkeypatch.setattr(orchestrator_module, "search_cgfp", forbidden_retrieval)

    response = await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", question="Ai-je droit à cette disponibilité ?"),
        "00000000-0000-0000-0000-000000000001",
    )

    assert response.clarification_question == "Êtes-vous fonctionnaire titulaire ou agent contractuel ?"
    assert response.answer == response.clarification_question
    assert response.sources == []


def test_vector_search_uses_ask_request_not_undefined_payload():
    source = inspect.getsource(LegalOrchestrator.ask)
    tree = ast.parse(source)
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "payload" not in names
    assert "request" in names
