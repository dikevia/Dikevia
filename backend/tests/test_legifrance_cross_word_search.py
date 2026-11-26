import json
from datetime import date

import httpx
import pytest

from app.config import settings
from app.legifrance import LegifranceConnector


def test_loda_cross_search_field_uses_documented_nested_query_shape():
    field = LegifranceConnector._loda_cross_search_field(
        "régime indemnitaire fonctions supplémentaires"
    )
    assert field == {
        "typeChamp": "ALL",
        "criteres": [{
            "criteres": [{
                "typeRecherche": "UN_DES_MOTS",
                "valeur": "régime",
                "operateur": "ET",
            }],
            "operateur": "ET",
            "proximite": 2,
            "typeRecherche": "UN_DES_MOTS",
            "valeur": "indemnitaire",
        }],
        "operateur": "ET",
    }


@pytest.mark.asyncio
async def test_loda_regulatory_search_uses_cross_word_fallback_only_after_zero_hits(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    search_payloads = []
    text_id = "LEGITEXT000012345678"

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            payload = json.loads(request.content)
            search_payloads.append(payload)
            if len(search_payloads) < 3:
                return httpx.Response(200, json={"results": []})
            criterion = payload["recherche"]["champs"][0]["criteres"][0]
            assert criterion["typeRecherche"] == "UN_DES_MOTS"
            assert criterion["proximite"] == 2
            assert criterion["criteres"][0]["valeur"] == "régime"
            return httpx.Response(200, json={"results": [{
                "id": text_id, "titre": "Décret relatif au régime indemnitaire",
                "nature": "DECRET",
            }]})
        if request.url.path.endswith("/consult/legiPart"):
            return httpx.Response(200, json={
                "id": text_id,
                "texte": "Texte réglementaire officiel suffisamment long pour être retenu par le connecteur et son test automatisé."
            })
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_regulatory_texts(
        "régime indemnitaire fonctions supplémentaires", date(2025, 1, 1)
    )
    assert len(search_payloads) == 3
    assert len(results) == 1
    assert results[0]["source_id"] == text_id
