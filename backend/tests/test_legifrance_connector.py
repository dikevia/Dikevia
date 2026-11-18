from datetime import date
import httpx
import pytest
from app.config import settings
from app.legifrance import LegifranceConnector, LegifranceUnavailable

ARTICLE_ID = "LEGIARTI000012345678"

@pytest.mark.asyncio
async def test_legifrance_oauth_ping_and_article_roundtrip(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_environment", "sandbox")
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    seen = []
    def handler(request):
        seen.append((request.method, request.url.path))
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/list/ping"):
            assert request.headers["Authorization"] == "Bearer unit-token"
            return httpx.Response(200, json={"status": "ok"})
        if request.url.path.endswith("/search"):
            body = __import__("json").loads(request.content)
            assert body["fond"] == "CODE_DATE"
            assert body["recherche"]["filtres"][1]["singleDate"] == 1763251200000
            return httpx.Response(200, json={"results": [{"id": ARTICLE_ID}]})
        if request.url.path.endswith("/consult/getArticle"):
            return httpx.Response(200, json={"id": ARTICLE_ID, "article": {"texte": "Article L. 123-4 Le texte réglementaire officiel est ici suffisamment long pour le test."}})
        return httpx.Response(404)
    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    assert await connector.ping() is True
    results = await connector.search_code_articles("article L. 123-4", date(2025, 11, 16))
    assert len(results) == 1
    assert results[0]["source_id"] == ARTICLE_ID
    assert results[0]["article"] == "L123-4"
    assert any(path.endswith("/search") for _, path in seen)

@pytest.mark.asyncio
async def test_legifrance_rejects_incomplete_oauth(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "")
    monkeypatch.setattr(settings, "legifrance_client_secret", "")
    connector = LegifranceConnector()
    with pytest.raises(LegifranceUnavailable):
        await connector.ping()

def test_legifrance_search_payload_uses_code_date_and_article_number(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_code_name", "Code général de la fonction publique")
    payload = LegifranceConnector()._search_payload("article L. 123-4", date(2025, 1, 1))
    assert payload["fond"] == "CODE_DATE"
    assert payload["recherche"]["champs"][0]["criteres"][0]["valeur"] == "L123-4"



@pytest.mark.asyncio
async def test_legifrance_exact_article_query_rejects_consulted_body_for_another_article(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": [{"id": ARTICLE_ID}]})
        if request.url.path.endswith("/consult/getArticle"):
            return httpx.Response(200, json={"id": ARTICLE_ID, "article": {
                "texte": "Article L. 123-5 Le texte officiel est suffisamment long pour ce test."
            }})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_code_articles("article L. 123-4", date(2025, 1, 1))
    assert results == []



def test_legifrance_article_consultation_is_bounded_to_five_ids():
    payload = {"results": [{"id": f"LEGIARTI{i:012d}"} for i in range(1, 12)]}
    ids = LegifranceConnector._find_article_ids(payload)
    assert len(ids) == 5
    assert ids[0] == "LEGIARTI000000000001"



def test_loda_excerpt_selects_relevant_sentences_instead_of_only_the_document_start():
    irrelevant = "Dispositions générales sans rapport avec la question. " * 60
    relevant = (
        "La durée annuelle du temps de travail des agents territoriaux est fixée "
        "dans les conditions prévues par les textes applicables."
    )
    excerpt = LegifranceConnector._relevant_excerpt(
        irrelevant + relevant, "durée annuelle temps de travail agents territoriaux"
    )
    assert len(excerpt) <= 1800
    assert "durée annuelle du temps de travail" in excerpt


def test_dated_versions_keep_official_id_and_have_distinct_citation_ids():
    from app.orchestrator import _tag_official_versions, _compare_official_period_versions

    start = date(2024, 1, 1)
    end = date(2025, 1, 1)
    start_sources = _tag_official_versions([{
        "source_type": "LEGIFRANCE_API", "source_id": ARTICLE_ID,
        "article": "L123-4", "text": "Ancienne rédaction officielle de l'article."
    }], start, "START")
    end_sources = _tag_official_versions([{
        "source_type": "LEGIFRANCE_API", "source_id": ARTICLE_ID,
        "article": "L123-4", "text": "Nouvelle rédaction officielle de l'article."
    }], end, "END")

    assert start_sources[0]["source_id"] != end_sources[0]["source_id"]
    assert start_sources[0]["official_source_id"] == ARTICLE_ID
    assert end_sources[0]["requested_effective_date"] == "2025-01-01"
    comparison = _compare_official_period_versions(start_sources, end_sources, start, end)
    assert comparison["changed_text_count"] == 1
    assert comparison["status"] == "ENDPOINTS_COMPARED_NOT_COMPLETE_HISTORY"
    assert "modifications intermédiaires" in comparison["limitation"]


def test_version_comparison_does_not_treat_missing_endpoint_result_as_repeal():
    from app.orchestrator import _tag_official_versions, _compare_official_period_versions

    start = date(2024, 1, 1)
    end = date(2025, 1, 1)
    only_start = _tag_official_versions([{
        "source_type": "LEGIFRANCE_LODA", "source_id": "LEGITEXT000012345678",
        "source_version_id": "LEGITEXT000012345678", "full_text": "Texte intégral suffisamment long."
    }], start, "START")
    comparison = _compare_official_period_versions(only_start, [], start, end)
    assert comparison["start_only_search_count"] == 1
    assert comparison["results"][0]["comparison"] == "FOUND_ONLY_IN_START_SEARCH"
    assert "Un résultat retrouvé à une seule borne ne prouve" in comparison["limitation"]
