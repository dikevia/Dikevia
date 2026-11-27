import ast
import inspect
import textwrap

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



@pytest.mark.parametrize("versant", ["FPE", "FPH"])
@pytest.mark.asyncio
async def test_non_territorial_scope_clarification_stops_retrieval(monkeypatch, versant):
    captured = {}

    async def ask_plan(**kwargs):
        captured["public_service"] = kwargs["legal_context"]["versant_fonction_publique"]
        return LegalResearchPlan(
            queries=[],
            legal_issues=[],
            clarification_needed="Votre employeur est-il un établissement public de santé, une collectivité ou un employeur privé ?",
        )

    async def forbidden_retrieval(*args, **kwargs):
        pytest.fail("La recherche ne doit pas démarrer avant la clarification du versant.")

    monkeypatch.setattr(orchestrator_module, "plan_legal_research", ask_plan)
    monkeypatch.setattr(orchestrator_module, "search_cgfp", forbidden_retrieval)

    response = await LegalOrchestrator().ask(
        AskRequest(
            employer="NATIONAL",
            public_service=versant,
            question="Je travaille comme infirmière à l'hôpital. Quels sont mes droits ?",
        ),
        "00000000-0000-0000-0000-000000000001",
    )

    assert captured["public_service"] == versant
    assert response.clarification_question.startswith("Votre employeur")
    assert response.answer == response.clarification_question
    assert response.sources == []


def test_vector_search_uses_ask_request_not_undefined_payload():
    source = inspect.getsource(LegalOrchestrator.ask)
    tree = ast.parse(textwrap.dedent(source))
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "payload" not in names
    assert "request" in names



def test_chat_ask_does_not_hold_a_transaction_during_orchestration():
    from pathlib import Path

    source = Path(__file__).parents[1].joinpath("app", "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    ask_node = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "ask"
    )
    ask_source = ast.get_source_segment(source, ask_node)
    assert "Depends(get_tenant_identity)" in ask_source
    assert "async with conn.transaction()" in ask_source
    assert "scoped_reader = _TenantScopedReadConnection(pool, ctx)" in ask_source
    assert "orchestrator.ask(" in ask_source
    assert "ctx.conn" not in ask_source
    # The route has two short DB transactions, with the external orchestration
    # call strictly between them rather than inside either transaction.
    first_tx = ask_source.index("async with conn.transaction()")
    orchestration = ask_source.index("orchestrator.ask(")
    second_tx = ask_source.rindex("async with conn.transaction()")
    assert first_tx < orchestration < second_tx


def test_orchestrator_read_adapter_reapplies_transaction_local_rls_context():
    from pathlib import Path

    source = Path(__file__).parents[1].joinpath("app", "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    adapter = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_TenantScopedReadConnection"
    )
    fetch_method = next(
        node for node in adapter.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "fetch"
    )
    fetch_source = ast.get_source_segment(source, fetch_method)
    assert "self._pool.acquire()" in fetch_source
    assert "conn.transaction()" in fetch_source
    assert "_set_tenant_rls_context(conn, self._ctx)" in fetch_source
    assert "conn.fetch(query, *args)" in fetch_source


@pytest.mark.asyncio
async def test_tenant_scoped_read_adapter_applies_all_rls_gucs_and_releases_connection():
    from types import SimpleNamespace

    from app.main import _TenantScopedReadConnection

    events = []

    class Transaction:
        async def __aenter__(self):
            events.append("transaction_enter")

        async def __aexit__(self, exc_type, exc, tb):
            events.append("transaction_exit")

    class Connection:
        def transaction(self):
            return Transaction()

        async def execute(self, query, value):
            events.append(("execute", query, value))

        async def fetch(self, query, *args):
            events.append(("fetch", query, args))
            return [{"ok": True}]

    class Acquire:
        async def __aenter__(self):
            events.append("acquire")
            return connection

        async def __aexit__(self, exc_type, exc, tb):
            events.append("release")

    class Pool:
        def acquire(self):
            return Acquire()

    connection = Connection()
    context = SimpleNamespace(
        principal=SimpleNamespace(issuer="issuer-A", subject="subject-A"),
        organization_id="org-A",
        user_id="user-A",
    )

    result = await _TenantScopedReadConnection(Pool(), context).fetch("SELECT 1", 42)

    assert result == [{"ok": True}]
    assert events[0:2] == ["acquire", "transaction_enter"]
    configured = [event for event in events if isinstance(event, tuple) and event[0] == "execute"]
    assert [event[2] for event in configured] == [
        "issuer-A", "subject-A", "org-A", "user-A"
    ]
    assert events[-3:] == [("fetch", "SELECT 1", (42,)), "transaction_exit", "release"]


def test_chat_orchestration_failure_response_is_safe_and_non_verified():
    from uuid import uuid4

    from app.main import _chat_orchestration_failure

    conversation_id = uuid4()
    response = _chat_orchestration_failure(conversation_id)

    assert response.conversation_id == conversation_id
    assert response.verification_status == "NON_VERIFIE"
    assert response.sources == []
    assert "incident temporaire" in response.answer
    assert "traceback" not in response.answer.lower()
    assert "exception" not in response.answer.lower()


def test_chat_route_persists_a_controlled_response_when_orchestration_raises():
    from pathlib import Path

    source = Path(__file__).parents[1].joinpath("app", "main.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    ask_node = next(
        node for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "ask"
    )
    ask_source = ast.get_source_segment(source, ask_node)
    assert "try:" in ask_source
    assert "except Exception:" in ask_source
    assert "_chat_orchestration_failure(conversation_id)" in ask_source
    assert "logger.error(" in ask_source
    assert "error_type=%s" in ask_source
    assert "INSERT INTO chat_messages" in ask_source
    assert "result.answer" in ask_source

@pytest.mark.asyncio
async def test_explicit_self_reported_other_versant_stops_research_before_retrieval(monkeypatch):
    async def forbidden_plan(**kwargs):
        pytest.fail("Aucune planification ne doit être lancée après un décalage explicite de versant.")

    async def forbidden_retrieval(*args, **kwargs):
        pytest.fail("Aucune recherche documentaire ne doit démarrer pour le mauvais versant.")

    monkeypatch.setattr(orchestrator_module, "plan_legal_research", forbidden_plan)
    monkeypatch.setattr(orchestrator_module, "search_cgfp", forbidden_retrieval)

    response = await LegalOrchestrator().ask(
        AskRequest(
            employer="NATIONAL",
            public_service="FPT",
            question="Je suis fonctionnaire de l'État et mon employeur refuse ma demande.",
        ),
        "00000000-0000-0000-0000-000000000001",
    )

    assert response.verification_status == "NON_VERIFIE"
    assert response.clarification_question
    assert "fonction publique de l'État" in response.clarification_question
    assert "nouvelle conversation" in response.answer
    assert response.sources == []

@pytest.mark.parametrize(
    ("versant", "label"),
    [("FPE", "fonction publique de l'État"), ("FPH", "fonction publique hospitalière")],
)
def test_non_territorial_compound_questions_keep_independent_research_axes(versant, label):
    from app.orchestrator import _build_versant_fallback_research

    question = "Mon congé maladie est refusé et ma prime n'est pas versée."
    queries, axes = _build_versant_fallback_research(question, versant)

    assert len(axes) == 2
    assert all(label in axis for axis in axes)
    assert all("décret 87-602" not in query and "décret 2002-60" not in query for query in queries)
    assert all("congé maladie" in axis or "rémunération" in axis for axis in axes)

def test_non_territorial_contract_and_discipline_question_keeps_both_axes():
    from app.orchestrator import _build_versant_fallback_research

    queries, axes = _build_versant_fallback_research(
        "Mon contrat arrive à son terme et une procédure disciplinaire est engagée.",
        "FPE",
    )

    assert len(axes) == 2
    assert any("contrat, renouvellement et fin de contrat" in axis for axis in axes)
    assert any("procédure disciplinaire et sanctions" in axis for axis in axes)
    assert all("fonction publique de l'État" in axis for axis in axes)

def test_provider_history_includes_previous_assistant_answer_only_when_explicitly_supplied():
    from app.orchestrator import _provider_context_history

    question = "Peux-tu détailler le deuxième point ?\nMon employeur refuse mes heures supplémentaires."
    assistant_context = "Le deuxième point concerne les conditions de récupération."

    history = _provider_context_history(
        question, True, assistant_context=assistant_context,
    )
    assert history == [
        {"role": "user", "content": "Mon employeur refuse mes heures supplémentaires."},
        {"role": "assistant", "content": assistant_context},
    ]
    assert _provider_context_history(question, False, assistant_context) == []


@pytest.mark.parametrize(
    ("versant", "employer", "expected"),
    [
        ("FPT", "VILLE_SAINT_ETIENNE", True),
        ("FPT", "SAINT_ETIENNE_METROPOLE", True),
        ("FPT", "NATIONAL", False),
        ("FPE", "VILLE_SAINT_ETIENNE", False),
        ("FPE", "SAINT_ETIENNE_METROPOLE", False),
        ("FPH", "VILLE_SAINT_ETIENNE", False),
        ("FPH", "SAINT_ETIENNE_METROPOLE", False),
        ("FPH", "NATIONAL", False),
    ],
)
def test_local_collectivity_documents_are_retrieved_only_for_fpt_employers(
    versant, employer, expected,
):
    from app.orchestrator import _should_search_local_employer_documents

    assert _should_search_local_employer_documents(versant, employer) is expected


@pytest.mark.parametrize(
    ("versant", "employer", "expected"),
    [
        ("FPT", "VILLE_SAINT_ETIENNE", "VILLE_SAINT_ETIENNE"),
        ("FPT", "SAINT_ETIENNE_METROPOLE", "SAINT_ETIENNE_METROPOLE"),
        ("FPT", "NATIONAL", "NATIONAL"),
        ("FPE", "VILLE_SAINT_ETIENNE", "NATIONAL"),
        ("FPE", "SAINT_ETIENNE_METROPOLE", "NATIONAL"),
        ("FPH", "VILLE_SAINT_ETIENNE", "NATIONAL"),
        ("FPH", "SAINT_ETIENNE_METROPOLE", "NATIONAL"),
    ],
)
def test_fpe_fph_research_never_inherits_fpt_only_employer_selector(
    versant, employer, expected,
):
    from app.orchestrator import _effective_employer_for_versant

    assert _effective_employer_for_versant(versant, employer) == expected


def test_all_ai_research_and_answer_stages_receive_versant_consistent_employer():
    import inspect

    from app.orchestrator import LegalOrchestrator

    source = inspect.getsource(LegalOrchestrator.ask)
    assert source.count(
        "_effective_employer_for_versant(request.public_service, request.employer)"
    ) == 4
