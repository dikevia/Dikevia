from datetime import date

import pytest

from app.instances import prepare_instance_with_legal_sources


class FakeLegifrance:
    configured = True

    def __init__(self):
        self.code_queries = []
        self.regulatory_queries = []

    async def search_code_articles(self, query, effective_date):
        self.code_queries.append((query, effective_date))
        return [{
            "source_type": "LEGIFRANCE_API",
            "source_id": "LEGIARTI000000000001",
            "article": "L123-1",
            "title": "Code général de la fonction publique — L123-1",
            "text": "Dispositions applicables aux agents publics. " * 8,
            "excerpt": "Dispositions applicables aux agents publics.",
            "effective_date_requested": effective_date.isoformat(),
            "official_source": True,
            "source_url": "https://www.legifrance.gouv.fr/",
        }]

    async def search_regulatory_texts(self, query, effective_date, limit=10):
        self.regulatory_queries.append((query, effective_date, limit))
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000000000001",
            "title": "Décret relatif aux instances territoriales",
            "official_number": "2021-571",
            "excerpt": "Dispositions réglementaires relatives aux instances.",
            "full_text": "Dispositions réglementaires relatives aux instances. " * 8,
            "official_url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000001",
            "version_status": "UNKNOWN",
            "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
        }]


class FakeCaseLaw:
    def __init__(self):
        self.queries = []

    async def search(self, query, effective_date):
        self.queries.append((query, effective_date))
        return [{
            "source_type": "LEGIFRANCE_CETAT_SEARCH",
            "source_id": "CETATEXT000000000001",
            "title": "Décision administrative relative au dialogue social",
            "decision_date": "2024-01-15",
            "excerpt": "Extrait de la décision.",
            "full_text_retrieved": False,
            "official_source": True,
            "source_url": "https://www.legifrance.gouv.fr/search/cetat",
        }]


@pytest.mark.asyncio
async def test_instance_preparation_reuses_all_three_existing_piste_search_families():
    legal = FakeLegifrance()
    case_law = FakeCaseLaw()
    effective_date = date(2026, 11, 27)

    result = await prepare_instance_with_legal_sources(
        "CST",
        "Organisation du travail et conditions de travail",
        legifrance_connector=legal,
        case_law_connector=case_law,
        effective_date=effective_date,
    )

    assert result["legal_conclusion"] is False
    assert result["legal_research"]["provider"] == "PISTE_LEGIFRANCE"
    assert result["legal_research"]["status"] == "SEARCHED"
    assert [item["family"] for item in result["legal_research"]["sources"]] == [
        "cgfp", "textes_reglementaires", "jurisprudence_administrative"
    ]
    assert len(legal.code_queries) == 1
    assert len(legal.regulatory_queries) == 1
    assert len(case_law.queries) == 1
    assert all(call[1] == effective_date for call in (
        legal.code_queries[0], legal.regulatory_queries[0], case_law.queries[0]
    ))
    case_law_source = result["legal_research"]["sources"][2]
    assert case_law_source["full_text_retrieved"] is False
    assert "métadonnées/extrait uniquement" in case_law_source["verification_note"]


@pytest.mark.asyncio
async def test_instance_preparation_keeps_lexical_checklist_when_piste_is_not_configured():
    class Unconfigured:
        configured = False

    result = await prepare_instance_with_legal_sources(
        "FS",
        "Risques psychosociaux et charge de travail",
        legifrance_connector=Unconfigured(),
        case_law_connector=FakeCaseLaw(),
        effective_date=date(2026, 11, 27),
    )

    assert result["points"]
    assert result["legal_research"]["status"] == "NOT_CONFIGURED"
    assert result["legal_research"]["sources"] == []


@pytest.mark.asyncio
async def test_instance_preparation_reports_partial_piste_failures_without_losing_other_sources():
    class PartlyUnavailable(FakeLegifrance):
        async def search_regulatory_texts(self, query, effective_date, limit=10):
            raise RuntimeError("upstream unavailable")

    legal = PartlyUnavailable()
    case_law = FakeCaseLaw()
    result = await prepare_instance_with_legal_sources(
        "CCP",
        "Non-renouvellement d'un agent contractuel",
        legifrance_connector=legal,
        case_law_connector=case_law,
        effective_date=date(2026, 11, 27),
    )

    assert result["legal_research"]["status"] == "PARTIAL"
    assert len(result["legal_research"]["sources"]) == 2
    regulatory = next(
        item for item in result["legal_research"]["searches"]
        if item["family"] == "TEXTES_REGLEMENTAIRES"
    )
    assert regulatory["status"] == "ERROR"
    assert regulatory["error_type"] == "RuntimeError"
