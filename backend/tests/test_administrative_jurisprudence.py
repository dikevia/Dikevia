from datetime import date
import httpx
import pytest

from app.config import settings
from app.legifrance import LegifranceConnector
from app.jurisprudence import AdministrativeCaseLawConnector


@pytest.mark.asyncio
async def test_cetat_search_uses_official_fund_and_returns_only_grounded_ids(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "secret")
    def handler(request):
        if request.url.path.endswith("/api/oauth/token"):
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            import json
            body = json.loads(request.content)
            assert body["fond"] == "CETAT"
            assert body["recherche"]["filtres"][0]["facette"] == "DATE_DECISION"
            assert body["recherche"]["filtres"][0]["dates"]["end"] == "2025-06-30"
            return httpx.Response(200, json={"results": [
                {"id": "CETATEXT000012345678", "titre": "Décision de test",
                 "dateDecision": "2024-05-10", "texte": "Extrait officiel de la décision."},
                {"id": "NOT_A_CETAT_ID", "titre": "Ignoré"},
                {"id": "CETATEXT000012345678", "titre": "Doublon"},
            ]})
        return httpx.Response(404)
    api = LegifranceConnector(transport=httpx.MockTransport(handler))
    connector = AdministrativeCaseLawConnector(api)
    results = await connector.search("temps de travail fonction publique", date(2025, 6, 30))
    assert len(results) == 1
    assert results[0]["source_id"] == "CETATEXT000012345678"
    assert results[0]["decision_date"] == "2024-05-10"
    assert results[0]["full_text_retrieved"] is False
    assert results[0]["text"] == "Extrait officiel de la décision."


def test_cetat_search_payload_has_bounded_page_and_date_range():
    payload = AdministrativeCaseLawConnector.search_payload("congés annuels", date(2025, 1, 1))
    assert payload["fond"] == "CETAT"
    assert payload["recherche"]["pageSize"] == 10
    assert payload["recherche"]["filtres"][0]["dates"] == {
        "start": "1900-01-01", "end": "2025-01-01"
    }


@pytest.mark.asyncio
async def test_cetat_rejects_too_short_query():
    connector = AdministrativeCaseLawConnector(LegifranceConnector())
    with pytest.raises(ValueError):
        await connector.search(" ", date(2025, 1, 1))

@pytest.mark.asyncio
async def test_consult_returns_full_text_only_when_official_identifier_matches(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "secret")
    full_text = "Considérant que l'administration doit respecter les garanties applicables. " * 4
    def handler(request):
        if request.url.path.endswith("/api/oauth/token"):
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        if request.url.path.endswith("/consult/juri"):
            import json
            assert json.loads(request.content) == {"textId": "CETATEXT000012345678"}
            return httpx.Response(200, json={"text": {
                "id": "CETATEXT000012345678", "titre": "Décision vérifiée",
                "dateDecision": "2024-05-10", "texte": full_text,
            }})
        return httpx.Response(404)
    connector = AdministrativeCaseLawConnector(LegifranceConnector(transport=httpx.MockTransport(handler)))
    result = await connector.consult("CETATEXT000012345678")
    assert result["full_text_retrieved"] is True
    assert result["source_status"] == "OFFICIAL_FULL_TEXT_ID_MATCHED"
    assert result["decision_date"] == "2024-05-10"
    assert result["text"].startswith("Considérant")


@pytest.mark.asyncio
async def test_consult_rejects_mismatched_official_identifier(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "secret")
    def handler(request):
        if request.url.path.endswith("/api/oauth/token"):
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        return httpx.Response(200, json={"text": {
            "id": "CETATEXT000099999999", "texte": "Texte suffisamment long. " * 10
        }})
    connector = AdministrativeCaseLawConnector(LegifranceConnector(transport=httpx.MockTransport(handler)))
    with pytest.raises(Exception, match="texte intégral vérifiable"):
        await connector.consult("CETATEXT000012345678")


def test_consult_rejects_malformed_decision_id():
    connector = AdministrativeCaseLawConnector(LegifranceConnector())
    with pytest.raises(ValueError):
        import asyncio
        asyncio.run(connector.consult("not-an-official-id"))



@pytest.mark.asyncio
async def test_cetat_full_text_ingestion_is_disabled_until_piste_contract_is_validated(monkeypatch):
    from fastapi import HTTPException
    from app.main import app
    route = next(r for r in app.routes
                 if getattr(r, "path", None) == "/api/v1/platform/legal-corpus/ingest/administrative-case-law")
    monkeypatch.setattr(settings, "legifrance_cetat_fulltext_enabled", False)
    with pytest.raises(HTTPException) as exc:
        await route.endpoint(q="temps de travail", effective_date=None, limit=10, admin=object())
    assert exc.value.status_code == 503
    assert "désactivé jusqu'à validation" in exc.value.detail



@pytest.mark.asyncio
async def test_administrative_connector_rejects_judicial_juritext_identifiers():
    connector = AdministrativeCaseLawConnector(LegifranceConnector())
    with pytest.raises(ValueError):
        await connector.consult("JURITEXT000012345678")
