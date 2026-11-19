import json
import pytest

from app.orchestrator import LegalOrchestrator
from app.schemas import AskRequest


async def _fake_piste_token(self):
    return "test-access-token"


@pytest.mark.asyncio
async def test_live_legifrance_success_does_not_query_snapshot(monkeypatch):
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
        source = next(s for s in kwargs["sources"] if s["source_type"] == "LEGIFRANCE_LODA")
        quote = " ".join(source["excerpt"].split())[:120]
        return json.dumps({"claims": [{
            "text": "Le décret n° 2024-100 doit être examiné au regard des faits.",
            "source_id": source["source_id"],
            "quote": quote,
        }]}, ensure_ascii=False)

    monkeypatch.setattr(module, "analyze_question", fake_ai)
    async def provider_available():
        return {"status": "AVAILABLE"}

    monkeypatch.setattr(module, "check_provider_availability", provider_available)
    async def supported_entailment(**kwargs):
        return {"valid": True, "invalid": []}

    monkeypatch.setattr(module, "verify_claim_entailment", supported_entailment)
    response = await LegalOrchestrator().ask(
        AskRequest(
            employer="NATIONAL", facts_date="2024-06-01",
            question="Quels sont les droits des agents ?",
        ),
        "00000000-0000-0000-0000-000000000001",
    )

    assert response.verification_status == "PARTIELLEMENT_VERIFIE"
    assert captured["sources"][0]["source_type"] == "LEGIFRANCE_LODA"
    assert not any(source["source_type"] == "CGFP_SNAPSHOT" for source in captured["sources"])
    assert any(source["source_type"] == "LEGIFRANCE_LODA" for source in captured["sources"])


@pytest.mark.asyncio
async def test_cgfp_snapshot_is_consulted_only_after_live_legifrance_failure(monkeypatch):
    import app.orchestrator as module
    from app.legifrance import LegifranceUnavailable

    monkeypatch.setattr(module.settings, "cgfp_enabled", True)
    monkeypatch.setattr(type(module.legifrance), "configured", property(lambda self: True))
    monkeypatch.setattr(type(module.legifrance), "_get_token", _fake_piste_token)

    call_order = []

    async def failed_live_code_search(*args, **kwargs):
        call_order.append("live-cgfp")
        raise LegifranceUnavailable("temporary upstream outage")

    async def live_regulatory_search(*args, **kwargs):
        call_order.append("live-loda")
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
        call_order.append("live-cetat")
        return []

    def snapshot_search(*args, **kwargs):
        call_order.append("snapshot")
        return {
            "source": {
                "snapshot_modified_at": "2026-10-31",
                "verification_status": "SNAPSHOT_NOT_LIVE_VERIFIED",
                "source_file": "CGFP_snapshot_2026-10-31.pdf",
            },
            "results": [{
                "article": "L123-4", "source_id": "FR-CGFP-2026-10-31",
                "page_start": 10, "page_end": 10, "excerpt": "Extrait du CGFP",
            }],
        }

    monkeypatch.setattr(module.legifrance, "search_code_articles", failed_live_code_search)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", live_regulatory_search)
    monkeypatch.setattr(module.case_law_connector, "search", no_case_law)
    monkeypatch.setattr(module, "search_cgfp", snapshot_search)
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
        return json.dumps({"claims": []})

    async def provider_available():
        return {"status": "AVAILABLE"}

    monkeypatch.setattr(module, "analyze_question", fake_ai)
    monkeypatch.setattr(module, "check_provider_availability", provider_available)

    response = await LegalOrchestrator().ask(
        AskRequest(
            employer="NATIONAL", facts_date="2024-06-01",
            question="Quels sont les droits des agents ?",
        ),
        "00000000-0000-0000-0000-000000000001",
    )

    assert "live-cgfp" in call_order
    assert "live-loda" in call_order
    assert "live-cetat" in call_order
    assert call_order.index("snapshot") > max(
        call_order.index("live-cgfp"),
        call_order.index("live-loda"),
        call_order.index("live-cetat"),
    )
    assert any(
        source.get("source_type") == "CGFP_SNAPSHOT"
        and source.get("reference_role") == "BASELINE_CONTEXT_ONLY"
        for source in captured["sources"]
    )
    assert any("Mode de secours CGFP activé" in item for item in response.missing_information)
