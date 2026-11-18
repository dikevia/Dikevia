import pytest

from app.orchestrator import LegalOrchestrator
from app.schemas import AskRequest


async def _fake_piste_token(self):
    return "test-access-token"


@pytest.mark.asyncio
async def test_ai_receives_cgfp_baseline_before_date_verified_sources(monkeypatch):
    import app.orchestrator as module

    monkeypatch.setattr(module.settings, "cgfp_enabled", True)
    monkeypatch.setattr(type(module.legifrance), "configured", property(lambda self: True))
    monkeypatch.setattr(type(module.legifrance), "_get_token", _fake_piste_token)

    async def no_code_articles(*args, **kwargs):
        return []

    async def regulatory_texts(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000000000001",
            "title": "Décret officiel daté",
            "document_kind": "DECREE",
            "official_number": "2024-100",
            "official_url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000001",
            "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
            "full_text": "Texte officiel du décret relatif aux agents territoriaux. " * 20,
        }]

    async def no_case_law(*args, **kwargs):
        return []

    monkeypatch.setattr(module.legifrance, "search_code_articles", no_code_articles)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", regulatory_texts)
    monkeypatch.setattr(module.case_law_connector, "search", no_case_law)
    monkeypatch.setattr(module, "search_cgfp", lambda *args, **kwargs: {
        "source": {
            "snapshot_modified_at": "2026-10-31",
            "verification_status": "SNAPSHOT_NOT_LIVE_VERIFIED",
            "source_file": "CGFP_snapshot_2026-10-31.pdf",
        },
        "results": [{
            "article": "L123-4", "source_id": "FR-CGFP-2026-10-31",
            "page_start": 10, "page_end": 10, "excerpt": "Extrait du CGFP",
        }],
    })
    monkeypatch.setattr(module, "get_cgfp_article", lambda ref: {
        "text": "Texte complet de l'article L123-4."
    })
    monkeypatch.setattr(
        module, "validate_snapshot_citation",
        lambda citation, article: {
            "valid": True, "verification_scope": "snapshot_document_integrity_only"
        },
    )

    captured = {}

    async def fake_ai(**kwargs):
        captured["sources"] = kwargs["sources"]
        return "Le décret n° 2024-100 doit être appliqué à la date des faits."

    monkeypatch.setattr(module, "analyze_question", fake_ai)
    response = await LegalOrchestrator().ask(
        AskRequest(
            employer="NATIONAL", facts_date="2024-06-01",
            question="Quels sont les droits des agents ?",
        ),
        "00000000-0000-0000-0000-000000000001",
    )

    assert response.verification_status == "PARTIELLEMENT_VERIFIE"
    assert captured["sources"][0]["source_type"] == "CGFP_SNAPSHOT"
    assert captured["sources"][0]["reference_role"] == "BASELINE_CONTEXT_ONLY"
    assert captured["sources"][0]["temporal_status"] == "SNAPSHOT_ONLY_NOT_TEMPORALLY_VERIFIED"
    assert any(source["source_type"] == "LEGIFRANCE_LODA" for source in captured["sources"])
