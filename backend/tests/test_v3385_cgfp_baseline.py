import json
import pytest

from app.orchestrator import LegalOrchestrator
from app.schemas import AskRequest


async def _fake_piste_token(self):
    return "test-access-token"


@pytest.mark.asyncio
async def test_live_legifrance_success_uses_snapshot_as_article_discovery_only(monkeypatch):
    import app.orchestrator as module

    monkeypatch.setattr(module.settings, "cgfp_enabled", True)
    monkeypatch.setattr(type(module.legifrance), "configured", property(lambda self: True))
    monkeypatch.setattr(type(module.legifrance), "_get_token", _fake_piste_token)

    code_queries = []

    async def no_code_articles(*args, **kwargs):
        code_queries.append(args[0])
        return []

    async def regulatory_texts(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000000000001",
            "title": "Décret relatif aux droits des agents territoriaux",
            "document_kind": "DECREE",
            "official_number": "2024-100",
            "official_url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000001",
            "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
            "full_text": ("Le décret relatif aux droits des agents territoriaux et à la fonction publique territoriale. " * 20),
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
            "matched_concepts": ["droits des agents"],
        }],
    })
    monkeypatch.setattr(module, "get_cgfp_article", lambda ref: {
        "text": "Le présent article concerne les agents publics et les fonctionnaires."
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
    assert "article L123-4" in code_queries
    assert any(source["source_type"] == "LEGIFRANCE_LODA" for source in captured["sources"])


@pytest.mark.asyncio
async def test_cgfp_snapshot_article_leads_are_verified_live_and_used_as_fallback_on_outage(monkeypatch):
    import app.orchestrator as module
    from app.legifrance import LegifranceUnavailable

    monkeypatch.setattr(module.settings, "cgfp_enabled", True)
    monkeypatch.setattr(type(module.legifrance), "configured", property(lambda self: True))
    monkeypatch.setattr(type(module.legifrance), "_get_token", _fake_piste_token)

    call_order = []
    code_queries = []

    async def failed_live_code_search(*args, **kwargs):
        call_order.append("live-cgfp")
        code_queries.append(args[0])
        raise LegifranceUnavailable("temporary upstream outage")

    async def live_regulatory_search(*args, **kwargs):
        call_order.append("live-loda")
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000000000001",
            "title": "Décret relatif aux droits des agents territoriaux",
            "document_kind": "DECREE",
            "official_number": "2024-100",
            "official_url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000001",
            "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
            "full_text": ("Le décret relatif aux droits des agents territoriaux et à la fonction publique territoriale. " * 20),
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
                "matched_concepts": ["droits des agents"],
            }],
        }

    monkeypatch.setattr(module.legifrance, "search_code_articles", failed_live_code_search)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", live_regulatory_search)
    monkeypatch.setattr(module.case_law_connector, "search", no_case_law)
    monkeypatch.setattr(module, "search_cgfp", snapshot_search)
    monkeypatch.setattr(module, "get_cgfp_article", lambda ref: {
        "text": "Le présent article concerne les agents publics et les fonctionnaires."
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
    assert call_order.index("snapshot") < call_order.index("live-cgfp")
    assert "article L123-4" in code_queries
    assert any(
        source.get("source_type") == "CGFP_SNAPSHOT"
        and source.get("reference_role") == "CGFP_SNAPSHOT_FALLBACK_EVIDENCE"
        for source in captured["sources"]
    )
    assert any("Mode de secours CGFP activé" in item for item in response.missing_information)



def test_cgfp_discovery_only_promotes_articles_with_fpt_or_common_scope(monkeypatch):
    import app.orchestrator as module

    found = {"results": [{
        "article": "L123-4",
        "matched_concepts": ["droits des agents"],
        "excerpt": "Extrait du CGFP",
    }]}

    monkeypatch.setattr(module, "get_cgfp_article", lambda ref: {
        "text": "Les fonctionnaires de l'État et les administrations centrales."
    })
    assert module._cgfp_article_discovery_queries(found) == []

    monkeypatch.setattr(module, "get_cgfp_article", lambda ref: {
        "text": "Le présent article concerne les agents publics et les fonctionnaires."
    })
    assert module._cgfp_article_discovery_queries(found) == ["article L123-4"]



def test_cgfp_fallback_never_uses_an_fpe_only_article(monkeypatch):
    import app.orchestrator as module

    monkeypatch.setattr(module, "get_cgfp_article", lambda ref: {
        "text": "Les fonctionnaires de l'État et les administrations centrales."
    })
    found = {"results": [{
        "article": "L999-1",
        "excerpt": "Protection fonctionnelle",
    }]}
    assert not module.should_use_cgfp_snapshot_fallback(
        "La recherche officielle CGFP a échoué.",
        found,
        "Mon employeur refuse ma protection fonctionnelle.",
    )



def test_cgfp_snapshot_fallback_can_support_only_snapshot_scoped_claims():
    from app.legal_assurance import validate_claim_evidence

    source = {
        "source_type": "CGFP_SNAPSHOT",
        "source_id": "FR-CGFP-2026-10-31:L521-1",
        "title": "Code général de la fonction publique — article L521-1",
        "article": "L521-1",
        "excerpt": (
            "Le présent article fixe les dispositions applicables aux agents "
            "territoriaux dans les conditions prévues par le code."
        ),
        "text": (
            "Le présent article fixe les dispositions applicables aux agents "
            "territoriaux dans les conditions prévues par le code."
        ),
        "content_kind": "SNAPSHOT_EXCERPT",
        "snapshot_modified_at": "2026-10-31",
        "source_status": "SNAPSHOT_NOT_LIVE_VERIFIED",
        "reference_role": "CGFP_SNAPSHOT_FALLBACK_EVIDENCE",
        "temporal_status": "SNAPSHOT_ONLY_NOT_TEMPORALLY_VERIFIED",
        "public_service_scope": "FPT_REFERENCE",
        "analysis_eligible": True,
        "claim_eligible": True,
        "citation_integrity": {"valid": True},
    }
    payload = {
        "claims": [{
            "text": "Le snapshot reproduit une disposition relative aux agents territoriaux.",
            "source_id": source["source_id"],
            "axis": "disposition CGFP",
            "quote": "dispositions applicables aux agents territoriaux",
        }],
        "uncovered_axes": [],
    }
    result = validate_claim_evidence(payload, [source], required_axes=["disposition CGFP"])
    assert result["valid"] is True
    assert result["claims"][0]["source_id"] == source["source_id"]

    baseline = {**source, "reference_role": "BASELINE_CONTEXT_ONLY"}
    rejected = validate_claim_evidence(payload, [baseline], required_axes=["disposition CGFP"])
    assert rejected["claims"] == []


def test_cgfp_snapshot_date_is_accepted_as_document_date_for_ai_input():
    from app.ai_provider import _usable_document_sources

    source = {
        "source_type": "CGFP_SNAPSHOT",
        "source_id": "FR-CGFP-2026-10-31:L521-1",
        "snapshot_modified_at": "2026-10-31",
        "source_status": "SNAPSHOT_NOT_LIVE_VERIFIED",
        "excerpt": "Un extrait de texte du CGFP suffisamment long pour être transmis.",
        "citation_integrity": {"valid": True},
    }
    assert _usable_document_sources([source]) == [
        {**source, "excerpt": "Un extrait de texte du CGFP suffisamment long pour être transmis."}
    ]
