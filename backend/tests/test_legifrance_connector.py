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
