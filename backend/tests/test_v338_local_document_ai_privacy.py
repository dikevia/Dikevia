import pytest

from app.ai_provider import _usable_document_sources
from app.config import Settings


def _local_source():
    return {
        "source_type": "LOCAL_DOCUMENT",
        "source_id": "LOCAL-DOC:123",
        "title": "Délibération locale",
        "effective_from": "2025-01-01",
        "excerpt": "Le temps de travail est organisé selon les modalités fixées par la collectivité.",
        "content_kind": "FULL_TEXT",
    }


def test_local_documents_are_excluded_from_chat_ai_by_default(monkeypatch):
    from app import ai_provider

    monkeypatch.setattr(ai_provider.settings, "ai_local_documents_in_chat_enabled", False)
    assert _usable_document_sources([_local_source()]) == []


def test_server_opt_in_alone_does_not_send_local_documents_without_request_consent(monkeypatch):
    from app import ai_provider

    monkeypatch.setattr(ai_provider.settings, "ai_local_documents_in_chat_enabled", True)
    result = _usable_document_sources([_local_source()], allow_local_documents=False)
    assert result == []


def test_local_documents_can_be_sent_after_server_opt_in_and_request_consent(monkeypatch):
    from app import ai_provider

    monkeypatch.setattr(ai_provider.settings, "ai_local_documents_in_chat_enabled", True)
    result = _usable_document_sources([_local_source()], allow_local_documents=True)
    assert len(result) == 1
    assert result[0]["source_id"] == "LOCAL-DOC:123"


def test_national_official_sources_remain_eligible_when_local_transfer_is_disabled(monkeypatch):
    from app import ai_provider

    monkeypatch.setattr(ai_provider.settings, "ai_local_documents_in_chat_enabled", False)
    official = {
        "source_type": "LEGIFRANCE_API",
        "source_id": "LEGIARTI000012345678",
        "requested_effective_date": "2025-01-01",
        "excerpt": "Le texte officiel prévoit les conditions applicables aux agents territoriaux.",
        "content_kind": "FULL_TEXT",
    }
    assert [item["source_id"] for item in _usable_document_sources([_local_source(), official])] == [
        "LEGIARTI000012345678"
    ]


def test_settings_default_to_no_local_document_ai_transfer():
    assert Settings(_env_file=None).ai_local_documents_in_chat_enabled is False


@pytest.mark.asyncio
async def test_entailment_verifier_fails_closed_for_local_document_without_opt_in(monkeypatch):
    from app import ai_provider

    monkeypatch.setattr(ai_provider.settings, "ai_local_documents_in_chat_enabled", False)
    monkeypatch.setattr(ai_provider.settings, "ai_api_key", "test-key")
    monkeypatch.setattr(ai_provider.settings, "ai_model", "test-model")
    monkeypatch.setattr(ai_provider.settings, "ai_api_base_url", "https://example.invalid/v1")
    result = await ai_provider.verify_claim_entailment(
        claims=[{"source_id": "LOCAL-DOC:123", "text": "Proposition de test"}],
        sources=[_local_source()],
    )
    assert result["valid"] is False
    assert result["invalid"] == ["claim_0:local_document_ai_transfer_disabled"]


def test_local_collectivity_document_source_family_is_also_blocked_by_default(monkeypatch):
    from app import ai_provider

    monkeypatch.setattr(ai_provider.settings, "ai_local_documents_in_chat_enabled", False)
    local = {**_local_source(), "source_type": "LOCAL_COLLECTIVITY_DOCUMENT"}
    assert _usable_document_sources([local]) == []


def test_dedicated_review_can_transfer_local_source_only_through_explicit_route_gate(monkeypatch):
    from app import ai_provider

    monkeypatch.setattr(ai_provider.settings, "ai_local_documents_in_chat_enabled", False)
    result = _usable_document_sources([_local_source()], allow_local_documents=True)
    assert [item["source_id"] for item in result] == ["LOCAL-DOC:123"]


def test_chat_request_consent_defaults_to_false():
    from app.schemas import AskRequest

    request = AskRequest(employer="NATIONAL", question="Question juridique de test")
    assert request.confirm_local_document_ai_transfer is False


def test_chat_transfer_requires_both_server_and_request_opt_in():
    import inspect
    from app.main import ask
    from app.orchestrator import LegalOrchestrator

    main_source = inspect.getsource(ask)
    orchestrator_source = inspect.getsource(LegalOrchestrator.ask)
    assert "payload.confirm_local_document_ai_transfer and settings.ai_local_documents_in_chat_enabled" in main_source
    assert '"confirm_local_document_ai_transfer": payload.confirm_local_document_ai_transfer' in main_source
    assert "allow_local_documents=allow_local_documents" in orchestrator_source

def test_historical_assistant_turns_with_local_sources_are_excluded_from_ai_context():
    from app.main import _ai_safe_conversation_history

    rows = [
        {"role": "assistant", "content": "Réponse fondée sur le droit national", "metadata": {
            "sources": [{"source_type": "LEGIFRANCE_API", "source_id": "LEGIARTI000012345678"}],
        }},
        {"role": "user", "content": "Ma question suivante", "metadata": {}},
        {"role": "assistant", "content": "Réponse avec extrait local", "metadata": {
            "sources": [{"source_type": "LOCAL_COLLECTIVITY_DOCUMENT", "source_id": "local-1"}],
        }},
    ]

    assert _ai_safe_conversation_history(rows) == [
        {"role": "user", "content": "Ma question suivante"},
        {"role": "assistant", "content": "Réponse fondée sur le droit national"},
    ]


def test_legacy_assistant_turn_without_source_provenance_is_excluded_from_ai_context():
    from app.main import _ai_safe_conversation_history

    rows = [
        {"role": "assistant", "content": "Ancienne réponse dont les sources sont inconnues", "metadata": None},
        {"role": "user", "content": "Question suivante", "metadata": {}},
    ]

    assert _ai_safe_conversation_history(rows) == [
        {"role": "user", "content": "Question suivante"},
    ]

def test_history_excludes_turn_when_local_source_was_beyond_persisted_source_preview():
    from app.main import _ai_safe_conversation_history

    rows = [
        {"role": "assistant", "content": "Réponse contenant un extrait local", "metadata": {
            "contains_local_documents": True,
            "sources": [{"source_type": "LEGIFRANCE_API", "source_id": "LEGIARTI000012345678"}],
        }},
        {"role": "user", "content": "Question suivante", "metadata": {}},
    ]

    assert _ai_safe_conversation_history(rows) == [
        {"role": "user", "content": "Question suivante"},
    ]
