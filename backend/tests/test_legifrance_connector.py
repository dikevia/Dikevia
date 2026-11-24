import json
from datetime import date, datetime, timezone
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
            assert body["recherche"]["filtres"][1]["singleDate"] == int(datetime(2025, 11, 16, tzinfo=timezone.utc).timestamp() * 1000)
            return httpx.Response(200, json={"results": [{"id": ARTICLE_ID}]})
        if request.url.path.endswith("/consult/getArticle"):
            return httpx.Response(200, json={"article": {"id": ARTICLE_ID, "num": "L. 123-4", "nomCode": "Code général de la fonction publique", "dateDebut": "2025-01-01", "texte": "Le texte réglementaire officiel est ici suffisamment long pour le test."}})
        return httpx.Response(404)
    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    assert await connector.ping() is True
    results = await connector.search_code_articles("article L. 123-4", date(2025, 11, 16))
    assert len(results) == 1
    assert results[0]["source_id"] == ARTICLE_ID
    assert results[0]["article"] == "L123-4"
    assert results[0]["valid_from"] == "2025-01-01"
    assert results[0]["requested_effective_date"] == "2025-11-16"
    assert results[0]["source_version_id"] == ARTICLE_ID
    assert any(path.endswith("/search") for _, path in seen)
    assert any(path.endswith("/list/ping") for _, path in seen)


@pytest.mark.parametrize(
    ("valid_from", "valid_to"),
    [
        ("2026-12-01", None),
        (None, "2026-11-18"),
    ],
)
@pytest.mark.asyncio
async def test_legifrance_rejects_article_validity_bounds_outside_requested_date(
    monkeypatch, valid_from, valid_to,
):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    requested_date = date(2026, 11, 19)

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            payload = json.loads(request.content)
            assert payload["fond"] == "CODE_DATE"
            assert payload["recherche"]["filtres"][1] == {
                "facette": "DATE_VERSION",
                "singleDate": int(datetime(2026, 11, 19, tzinfo=timezone.utc).timestamp() * 1000),
            }
            return httpx.Response(200, json={"results": [{"id": ARTICLE_ID}]})
        if request.url.path.endswith("/consult/getArticle"):
            article = {
                "id": ARTICLE_ID,
                "num": "L. 123-4",
                "nomCode": "Code général de la fonction publique",
                "texte": "Disposition officielle suffisamment longue pour le test.",
            }
            if valid_from is not None:
                article["dateDebut"] = valid_from
            if valid_to is not None:
                article["dateFin"] = valid_to
            return httpx.Response(200, json={"article": article})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    assert await connector.search_code_articles(
        "article L. 123-4", requested_date,
    ) == []


@pytest.mark.parametrize(
    ("requested_ref", "returned_num"),
    [
        ("L. 111-1", "L111-1"),
        ("l111-1", "L. 111-1"),
        ("L111-1", "l111-1"),
    ],
)
@pytest.mark.asyncio
async def test_legifrance_accepts_short_official_article_text_when_metadata_matches(
    monkeypatch, requested_ref, returned_num
):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    short_text = "La liberté d'opinion est garantie aux agents publics."

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": [{"id": ARTICLE_ID}]})
        if request.url.path.endswith("/consult/getArticle"):
            return httpx.Response(200, json={"article": {
                "id": ARTICLE_ID,
                "num": returned_num,
                "nomCode": "Code général de la fonction publique",
                "texte": short_text,
            }})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_code_articles(f"article {requested_ref}", date(2026, 11, 19))
    assert len(results) == 1
    assert results[0]["article"] == "L111-1"
    assert results[0]["text"] == short_text
    assert len(results[0]["text"]) == 53


@pytest.mark.asyncio
async def test_legifrance_uses_search_article_id_when_get_article_omits_num(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    short_text = "Disposition brève."

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": [{"id": ARTICLE_ID}]})
        if request.url.path.endswith("/consult/getArticle"):
            return httpx.Response(200, json={"article": {
                "id": ARTICLE_ID, "texte": short_text,
            }})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_code_articles("article L. 111-1", date(2026, 11, 19))
    assert len(results) == 1
    assert results[0]["source_id"] == ARTICLE_ID
    assert results[0]["article"] is None
    assert results[0]["text"] == short_text


@pytest.mark.asyncio
async def test_legifrance_second_code_civil_article_control(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    control_text = (
        "La partie envers laquelle l'engagement n'a pas été exécuté, ou l'a été imparfaitement, peut :\n"
        "- refuser d'exécuter ou suspendre l'exécution de sa propre obligation ;\n"
        "- poursuivre l'exécution forcée en nature de l'obligation ;\n"
        "- obtenir une réduction du prix ;\n"
        "- provoquer la résolution du contrat ;\n"
        "- demander réparation des conséquences de l'inexécution.\n"
        "Les sanctions qui ne sont pas incompatibles peuvent être cumulées ; des dommages et intérêts "
        "peuvent toujours s'y ajouter."
    )
    control_html = (
        "<p>La partie envers laquelle l'engagement n'a pas été exécuté, ou l'a été imparfaitement, peut :</p>"
        "<ul><li>refuser d'exécuter ou suspendre l'exécution de sa propre obligation ;</li>"
        "<li>poursuivre l'exécution forcée en nature de l'obligation ;</li>"
        "<li>obtenir une réduction du prix ;</li><li>provoquer la résolution du contrat ;</li>"
        "<li>demander réparation des conséquences de l'inexécution.</li></ul>"
        "<p>Les sanctions qui ne sont pas incompatibles peuvent être cumulées ; des dommages et intérêts "
        "peuvent toujours s'y ajouter.</p>"
    )

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            body = json.loads(request.content)
            assert body["recherche"]["filtres"][0]["valeurs"] == ["Code civil"]
            assert body["recherche"]["champs"][0]["typeChamp"] == "NUM_ARTICLE"
            assert body["recherche"]["champs"][0]["criteres"][0]["valeur"] == "1217"
            return httpx.Response(200, json={"results": [{"id": ARTICLE_ID}]})
        if request.url.path.endswith("/consult/getArticle"):
            return httpx.Response(200, json={"article": {
                "id": ARTICLE_ID, "num": "1217", "nomCode": "Code civil",
                "dateDebut": "2018-10-01", "texte": control_text, "texteHtml": control_html,
            }})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_code_articles(
        "article 1217", date(2026, 11, 19), code_name="Code civil"
    )
    assert len(results) == 1
    assert results[0]["article"] == "1217"
    assert results[0]["title"].startswith("Code civil")
    assert results[0]["text"] == control_text
    assert "\n- poursuivre l'exécution forcée en nature de l'obligation ;" in results[0]["text"]
    assert len(results[0]["text"]) > 0


@pytest.mark.asyncio
async def test_legifrance_nonexistent_article_returns_no_official_result(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": [], "totalResultNumber": 0})
        raise AssertionError("getArticle must not be called without a search result")

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_code_articles("article L999-999", date(2026, 11, 19))
    assert results == []


@pytest.mark.asyncio
async def test_legifrance_rejects_non_object_oauth_response(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json=[{"access_token": "unexpected"}])
        raise AssertionError("No API request is expected after invalid OAuth JSON")

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    with pytest.raises(LegifranceUnavailable, match="objet JSON attendu"):
        await connector.ping()


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
    assert payload["recherche"]["typePagination"] == "ARTICLE"
    free_text = LegifranceConnector()._search_payload(
        "régime indemnitaire fonctions supplémentaires", date(2025, 1, 1)
    )
    criterion = free_text["recherche"]["champs"][0]["criteres"][0]
    assert criterion["typeRecherche"] == "UN_DES_MOTS"
    assert criterion["proximite"] == 5
    precise = LegifranceConnector()._search_payload(
        "régime indemnitaire fonctions supplémentaires", date(2025, 1, 1), precise=True
    )
    precise_criterion = precise["recherche"]["champs"][0]["criteres"][0]
    assert precise_criterion["typeRecherche"] == "TOUS_LES_MOTS_DANS_UN_CHAMP"
    assert precise_criterion["proximite"] == 5
    # Exact article references stay exact regardless of keyword mode.
    exact = LegifranceConnector()._search_payload(
        "article L. 123-4", date(2025, 1, 1), precise=True
    )
    assert exact["recherche"]["champs"][0]["criteres"][0]["typeRecherche"] == "EXACTE"
    assert payload["recherche"]["filtres"][1]["singleDate"] == LegifranceConnector._date_epoch_ms(date(2025, 1, 1))



@pytest.mark.asyncio
async def test_legifrance_regulatory_search_uses_broad_mode_only_after_precise_zero_hits(monkeypatch):
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
            if len(search_payloads) == 1:
                return httpx.Response(200, json={"results": []})
            return httpx.Response(200, json={"results": [{
                "id": text_id, "titre": "Décret relatif au régime indemnitaire"
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
    assert len(results) == 1
    assert len(search_payloads) == 2
    first = search_payloads[0]["recherche"]["champs"][0]["criteres"][0]
    second = search_payloads[1]["recherche"]["champs"][0]["criteres"][0]
    assert first["typeRecherche"] == "TOUS_LES_MOTS_DANS_UN_CHAMP"
    assert second["typeRecherche"] == "UN_DES_MOTS"


@pytest.mark.asyncio
async def test_legifrance_code_search_uses_broad_mode_only_after_precise_zero_hits(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    search_payloads = []

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            payload = json.loads(request.content)
            search_payloads.append(payload)
            if len(search_payloads) == 1:
                return httpx.Response(200, json={"results": []})
            return httpx.Response(200, json={"results": [{"id": ARTICLE_ID}]})
        if request.url.path.endswith("/consult/getArticle"):
            return httpx.Response(200, json={"article": {
                "id": ARTICLE_ID, "num": "L123-4",
                "nomCode": "Code général de la fonction publique",
                "texte": "Disposition officielle suffisamment longue pour être conservée dans le résultat de test."
            }})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_code_articles(
        "régime indemnitaire fonctions supplémentaires", date(2025, 1, 1)
    )
    assert len(results) == 1
    assert len(search_payloads) == 2
    first = search_payloads[0]["recherche"]["champs"][0]["criteres"][0]
    second = search_payloads[1]["recherche"]["champs"][0]["criteres"][0]
    assert first["typeRecherche"] == "TOUS_LES_MOTS_DANS_UN_CHAMP"
    assert second["typeRecherche"] == "UN_DES_MOTS"


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
            return httpx.Response(200, json={"article": {
                "id": ARTICLE_ID, "num": "L123-5",
                "nomCode": "Code général de la fonction publique",
                "texte": "Le texte officiel est suffisamment long pour ce test."
            }})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_code_articles("article L. 123-4", date(2025, 1, 1))
    assert results == []



def test_legifrance_article_consultation_keeps_all_ten_search_hits():
    payload = {"results": [{"titles": [{"id": f"LEGIARTI{i:012d}", "cid": f"LEGIARTI{i:012d}"}]}
                          for i in range(1, 12)]}
    ids = LegifranceConnector._find_article_ids(payload)
    assert len(ids) == 10
    assert ids[0] == "LEGIARTI000000000001"
    assert ids[-1] == "LEGIARTI000000000010"


def test_legifrance_text_extraction_keeps_distinct_sibling_segments_without_duplicates():
    payload = {"article": {"texte": "Article A complet.", "children": [
        {"texte": "Article B complet."},
        {"texte": "Article A complet."},
    ]}}
    extracted = LegifranceConnector._extract_text(payload)
    assert "Article A complet." in extracted
    assert "Article B complet." in extracted
    assert extracted.count("Article A complet.") == 1



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
    assert set(comparison["matched_source_ids"]) == {
        start_sources[0]["source_id"], end_sources[0]["source_id"]
    }
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
    assert "ne prouve pas l'abrogation ou l'inapplicabilité" in comparison["limitation"]


def test_loda_comparison_does_not_merge_different_instrument_kinds_with_same_number():
    from app.orchestrator import _tag_official_versions, _compare_official_period_versions

    start = date(2024, 1, 1)
    end = date(2025, 1, 1)
    start_sources = _tag_official_versions([
        {
            "source_type": "LEGIFRANCE_LODA", "source_id": "LEGITEXT000000000001",
            "source_version_id": "LEGITEXT000000000001", "document_kind": "LAW",
            "official_number": "2024-1", "full_text": "Texte de loi suffisamment long."
        },
        {
            "source_type": "LEGIFRANCE_LODA", "source_id": "LEGITEXT000000000002",
            "source_version_id": "LEGITEXT000000000002", "document_kind": "DECREE",
            "official_number": "2024-1", "full_text": "Texte de décret suffisamment long."
        },
    ], start, "START")
    end_sources = _tag_official_versions([{
        "source_type": "LEGIFRANCE_LODA", "source_id": "LEGITEXT000000000001",
        "source_version_id": "LEGITEXT000000000001", "document_kind": "LAW",
        "official_number": "2024-1", "full_text": "Texte de loi modifié suffisamment long."
    }], end, "END")

    comparison = _compare_official_period_versions(start_sources, end_sources, start, end)
    assert comparison["changed_text_count"] == 1
    assert comparison["start_only_search_count"] == 1
    assert any(item["comparison"] == "FOUND_ONLY_IN_START_SEARCH" for item in comparison["results"])


def test_non_api_sources_need_explicit_validity_covering_the_whole_period():
    from app.orchestrator import _source_covers_period

    start = date(2024, 1, 1)
    end = date(2025, 1, 1)
    assert _source_covers_period(
        {"valid_from": "2020-01-01", "valid_to": "2025-01-01"}, start, end
    )
    assert not _source_covers_period(
        {"valid_from": "2024-06-01", "valid_to": "2025-12-31"}, start, end
    )
    assert not _source_covers_period(
        {"valid_to": "2025-12-31"}, start, end
    )
    assert not _source_covers_period(
        {"valid_from": "2020-01-01", "valid_to": None}, start, end
    )


def test_code_article_excerpt_selects_relevant_sentences_not_only_the_beginning():
    irrelevant = "Dispositions générales sans rapport avec les heures supplémentaires. " * 50
    relevant = (
        "Les indemnités horaires pour travaux supplémentaires sont attribuées "
        "selon les conditions fixées par le texte applicable."
    )
    excerpt = LegifranceConnector._relevant_excerpt(
        irrelevant + relevant, "indemnités horaires travaux supplémentaires"
    )
    assert len(excerpt) <= 1800
    assert "indemnités horaires pour travaux supplémentaires" in excerpt

@pytest.mark.asyncio
async def test_legifrance_ping_falls_back_to_consult_route_only_when_list_route_missing(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_environment", "sandbox")
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/list/ping"):
            return httpx.Response(404)
        if request.url.path.endswith("/consult/ping"):
            return httpx.Response(200, text="pong")
        return httpx.Response(500)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    assert await connector.ping() is True
    assert any(path.endswith("/list/ping") for path in seen)
    assert any(path.endswith("/consult/ping") for path in seen)


@pytest.mark.asyncio
async def test_legifrance_ping_falls_back_when_list_route_returns_upstream_500(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_environment", "production")
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/list/ping"):
            return httpx.Response(500, json={"error": "sensitive-upstream-detail"})
        if request.url.path.endswith("/consult/ping"):
            return httpx.Response(200, text="pong")
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    assert await connector.ping() is True
    assert any(path.endswith("/list/ping") for path in seen)
    assert any(path.endswith("/consult/ping") for path in seen)


@pytest.mark.parametrize("status_code", [401, 403])
@pytest.mark.asyncio
async def test_legifrance_ping_does_not_hide_auth_or_permission_failures(
    monkeypatch, status_code
):
    monkeypatch.setattr(settings, "legifrance_environment", "production")
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/list/ping"):
            return httpx.Response(status_code)
        if request.url.path.endswith("/consult/ping"):
            return httpx.Response(200, text="pong")
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    with pytest.raises(LegifranceUnavailable):
        await connector.ping()
    assert any(path.endswith("/list/ping") for path in seen)
    assert not any(path.endswith("/consult/ping") for path in seen)


@pytest.mark.asyncio
async def test_legifrance_ping_diagnostics_checks_all_routes_independently(monkeypatch, caplog):
    monkeypatch.setattr(settings, "legifrance_environment", "production")
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search/ping"):
            return httpx.Response(200, text="pong")
        if request.url.path.endswith("/consult/ping"):
            return httpx.Response(200, text="pong")
        if request.url.path.endswith("/list/ping"):
            return httpx.Response(500, json={"error": "upstream"})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.ping_diagnostics()
    assert results == {
        "search/ping": 200,
        "consult/ping": 200,
        "list/ping": 500,
    }
    assert "sensitive-upstream-detail" not in caplog.text


@pytest.mark.asyncio
async def test_loda_search_consults_matching_official_text_at_requested_date(monkeypatch):
    from datetime import datetime, timezone

    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    requested_date = date(2026, 11, 19)
    expected_stamp = int(datetime(2026, 11, 19, tzinfo=timezone.utc).timestamp() * 1000)
    full_text = (
        "Le présent décret fixe les conditions d'attribution des indemnités horaires "
        "pour travaux supplémentaires aux agents territoriaux. "
    ) * 3
    seen = []

    def handler(request):
        seen.append(request.url.path)
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            body = json.loads(request.content)
            assert body["fond"] == "LODA_DATE"
            assert body["recherche"]["champs"][0]["typeChamp"] == "NUM"
            assert body["recherche"]["champs"][0]["criteres"][0] == {
                "typeRecherche": "EXACTE", "valeur": "2002-60", "operateur": "ET"
            }
            assert body["recherche"]["filtres"][0] == {
                "facette": "DATE_VERSION", "singleDate": expected_stamp
            }
            return httpx.Response(200, json={"results": [{
                "titles": [{
                    "id": "LEGITEXT000012345678_01-01-2023",
                    "title": "Décret n° 2002-60 relatif aux indemnités horaires pour travaux supplémentaires",
                }],
                "nature": "DECRET",
                "nor": "FPPA0100150D",
                "date": "2002-01-14",
                "datePublication": "2002-01-15",
                "etat": "VIGUEUR",
            }]})
        if request.url.path.endswith("/consult/legiPart"):
            body = json.loads(request.content)
            assert body == {"date": expected_stamp, "textId": "LEGITEXT000012345678"}
            return httpx.Response(200, json={"text": {
                "id": "LEGITEXT000012345678_01-01-2023", "texte": full_text,
            }})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_regulatory_texts(
        "décret 2002-60 indemnités horaires pour travaux supplémentaires",
        requested_date,
        limit=3,
    )

    assert len(results) == 1
    source = results[0]
    assert source["source_type"] == "LEGIFRANCE_LODA"
    assert source["source_id"] == "LEGITEXT000012345678"
    assert source["document_kind"] == "DECREE"
    assert source["official_number"] == "2002-60"
    assert source["nor"] == "FPPA0100150D"
    assert source["title"].startswith("Décret n° 2002-60")
    assert source["signature_date"].isoformat() == "2002-01-14"
    assert source["source_status"] == "OFFICIAL_TEXT_ID_VERIFIED"
    assert source["version_status"] == "IN_FORCE"
    assert source["full_text"] == full_text.strip()
    assert "indemnités horaires" in source["excerpt"]
    assert any(path.endswith("/consult/legiPart") for path in seen)


@pytest.mark.asyncio
async def test_loda_search_rejects_mismatched_consulted_identifier(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            body = json.loads(request.content)
            assert body["recherche"]["champs"][0]["typeChamp"] == "ALL"
            assert body["recherche"]["champs"][0]["criteres"][0]["proximite"] == 5
            return httpx.Response(200, json={"results": [{
                "id": "LEGITEXT000012345678_01-01-2023",
                "titre": "Décret relatif aux agents territoriaux",
            }]})
        if request.url.path.endswith("/consult/legiPart"):
            return httpx.Response(200, json={"text": {
                "id": "LEGITEXT000099999999",
                "texte": "Texte officiel suffisamment long pour dépasser le seuil de validation. " * 3,
            }})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_regulatory_texts(
        "heures supplémentaires 2024-2025 agents territoriaux", date(2026, 11, 19)
    )
    assert results == []


@pytest.mark.asyncio
async def test_loda_exact_lookup_supports_two_digit_year_decree_numbers(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            body = json.loads(request.content)
            criterion = body["recherche"]["champs"][0]["criteres"][0]
            assert body["recherche"]["champs"][0]["typeChamp"] == "NUM"
            assert criterion == {
                "typeRecherche": "EXACTE", "valeur": "91-875", "operateur": "ET"
            }
            return httpx.Response(200, json={"results": []})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    assert await connector.search_regulatory_texts(
        "décret n° 91-875", date(2026, 11, 19)
    ) == []


@pytest.mark.asyncio
async def test_loda_exact_91_875_lookup_preserves_territorial_decree_number(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    full_text = (
        "Décret pris pour l'application de l'article L. 714-4 du CGFP. "
        "L'assemblée délibérante des collectivités territoriales fixe les conditions "
        "d'attribution des indemnités horaires pour travaux supplémentaires. "
    ) * 2

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            body = json.loads(request.content)
            assert body["recherche"]["champs"][0]["typeChamp"] == "NUM"
            assert body["recherche"]["champs"][0]["criteres"][0]["valeur"] == "91-875"
            return httpx.Response(200, json={"results": [{
                "titles": [{
                    "id": "LEGITEXT000052196548_01-07-2026",
                    "title": "Décret n°91-875 du 6 septembre 1991 pris pour l'application de l'article L. 714-4 du CGFP",
                }],
                "nature": "DECRET",
                "nor": "INTB9100377D",
                "date": "1991-09-06",
                "datePublication": "1991-09-07",
                "etat": "VIGUEUR",
            }]})
        if request.url.path.endswith("/consult/legiPart"):
            body = json.loads(request.content)
            assert body["textId"] == "LEGITEXT000052196548"
            return httpx.Response(200, json={"text": {
                "id": "LEGITEXT000052196548", "texte": full_text,
            }})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_regulatory_texts(
        "décret n° 91-875", date(2026, 11, 19)
    )
    assert len(results) == 1
    assert results[0]["official_number"] == "91-875"
    assert results[0]["nor"] == "INTB9100377D"
    assert results[0]["source_id"] == "LEGITEXT000052196548"
    assert results[0]["full_text"] == full_text.strip()


@pytest.mark.asyncio
async def test_regulatory_search_prefers_complete_requested_article_sections(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    text_id = "LEGITEXT000012345678"
    full_text = (
        "Préambule sans rapport avec la demande.\n"
        "Article 37-1\nDisposition antérieure sans rapport.\n"
        "Article 37-2\nDéclaration d'accident de service et certificat médical requis. "
        "L'agent adresse les pièces à l'autorité territoriale.\n"
        "Article 37-5\nL'autorité dispose d'un délai d'un mois pour instruire la déclaration.\n"
        "Article 37-9\nDisposition postérieure non demandée."
    )

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            payload = json.loads(request.content)
            criterion = payload["recherche"]["champs"][0]["criteres"][0]
            assert criterion["typeRecherche"] == "EXACTE"
            assert criterion["valeur"] == "87-602"
            return httpx.Response(200, json={"results": [{
                "id": text_id, "titre": "Décret n° 87-602 du 30 juillet 1987",
                "dateTexte": "1987-07-30",
            }]})
        if request.url.path.endswith("/consult/legiPart"):
            return httpx.Response(200, json={"id": text_id, "texte": full_text})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_regulatory_texts(
        "décret n° 87-602 articles 37-2 37-5 CITIS accident déclaration imputabilité",
        date(2026, 11, 22),
    )
    assert len(results) == 1
    assert "Article 37-2" in results[0]["excerpt"]
    assert "Article 37-5" in results[0]["excerpt"]
    assert "Article 37-1" not in results[0]["excerpt"]
    assert "Article 37-9" not in results[0]["excerpt"]
    assert results[0]["full_text"] == full_text


def test_requested_excerpt_extracts_targeted_amendments_from_long_decree_article():
    prefix = "Article 3\n" + ("Disposition générale sans lien avec le CITIS. " * 450)
    full_text = (
        prefix
        + "\n2° L'article 13-2 est remplacé par les dispositions suivantes :\n"
        + "« Art. 13-2. - La décision relative au temps partiel thérapeutique intervient au plus tard trente jours. »\n"
        + "3° L'article 13-5 est remplacé par les dispositions suivantes :\n"
        + "« Art. 13-5. - Les conclusions médicales peuvent être contestées devant le conseil médical. »\n"
        + "11° Le 2° de l'article 37-2 est remplacé par les dispositions suivantes :\n"
        + "« Un certificat médical indique la nature et le siège des lésions. »\n"
        + "12° Après l'article 37-9, il est inséré un article 37-9-1 ainsi rédigé :\n"
        + "« Art. 37-9-1. - Les dispositions des articles 26-1, 28, 31-2 et 34-1 s'appliquent au CITIS. »\n"
        + "13° Les articles 13-4, 13-6 et 37-15 sont abrogés."
    )
    citis = LegifranceConnector._requested_article_excerpt(
        full_text,
        "décret n° 2026-705 article 3 modifie articles 37-2 et 37-9-1 CITIS",
    )
    assert "nature et le siège des lésions" in citis
    assert "s'appliquent au CITIS" in citis
    assert "temps partiel thérapeutique" not in citis
    assert len(citis) < 5000

    tpt = LegifranceConnector._requested_article_excerpt(
        full_text,
        "décret n° 2026-705 article 3 modifie articles 13-2 et 13-5 temps partiel thérapeutique",
    )
    assert "trente jours" in tpt
    assert "contestées devant le conseil médical" in tpt
    assert "s'appliquent au CITIS" not in tpt


@pytest.mark.asyncio
async def test_legifrance_bounds_concurrent_requests_and_refreshes_oauth_once(monkeypatch):
    import asyncio

    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")

    class TrackingTransport(httpx.AsyncBaseTransport):
        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.token_calls = 0

        async def handle_async_request(self, request):
            self.active += 1
            self.max_active = max(self.max_active, self.active)
            try:
                await asyncio.sleep(0.005)
                if request.url.path == "/api/oauth/token":
                    self.token_calls += 1
                    return httpx.Response(
                        200, json={"access_token": "shared-token", "expires_in": 3600},
                        request=request,
                    )
                return httpx.Response(200, json={"ok": True}, request=request)
            finally:
                self.active -= 1

        async def aclose(self):
            return None

    transport = TrackingTransport()
    connector = LegifranceConnector(transport=transport)
    results = await asyncio.gather(*[
        connector._request("GET", "/diagnostic") for _ in range(16)
    ])

    assert len(results) == 16
    assert all(result == {"ok": True} for result in results)
    assert transport.token_calls == 1
    assert transport.max_active <= 4


@pytest.mark.parametrize(
    ("nature", "title", "expected"),
    [
        ("DECRET", "Texte réglementaire", "DECREE"),
        ("ARRETE", "Texte réglementaire", "ORDER"),
        ("LOI", "Texte législatif", "LAW"),
        ("ORDONNANCE", "Texte", "ORDONNANCE"),
        ("CIRCULAIRE", "Instruction", "CIRCULAR"),
        ("NATURE_INCONNUE", "Acte administratif non qualifié", "OTHER"),
        (None, "Décret n° 2002-60", "DECREE"),
        (None, "Loi n° 2024-100", "LAW"),
        (None, "Code général de la fonction publique", "CODE"),
        (None, "Acte administratif non qualifié", "OTHER"),
    ],
)
def test_loda_document_kind_uses_official_nature_and_never_defaults_unknown_to_law(
    nature, title, expected,
):
    from app.legifrance import _loda_document_kind

    assert _loda_document_kind(nature, title, None) == expected


@pytest.mark.parametrize(
    ("raw_status", "expected"),
    [
        ("VIGUEUR", "IN_FORCE"),
        ("ABROGE", "REPEALED"),
        ("ABROGÉ", "REPEALED"),
        ("PÉRIMÉ", "NOT_IN_FORCE"),
        ("NON EN VIGUEUR", "NOT_IN_FORCE"),
        ("PLUS EN VIGUEUR", "NOT_IN_FORCE"),
        ("ABROGÉ PARTIELLEMENT", "UNKNOWN"),
        ("VIGUEUR DIFFÉRÉE", "UNKNOWN"),
        (None, "UNKNOWN"),
    ],
)
def test_loda_version_status_does_not_promote_qualified_or_negative_labels(raw_status, expected):
    from app.legifrance import _loda_version_status

    assert _loda_version_status(raw_status) == expected

@pytest.mark.asyncio
async def test_code_article_keeps_compact_display_excerpt_and_expanded_analysis_excerpt(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    clauses = [
        f"La rémunération et les indemnités des agents sont encadrées par la disposition numéro {index}."
        for index in range(35)
    ]
    exception = "Toutefois, l'indemnité de rémunération n'est pas due lorsque les conditions prévues ne sont pas réunies."
    full_text = "\\n".join(["Article L. 123-4.", *clauses, exception])

    def handler(request):
        if request.url.path == "/api/oauth/token":
            return httpx.Response(200, json={"access_token": "unit-token", "expires_in": 3600})
        if request.url.path.endswith("/search"):
            return httpx.Response(200, json={"results": [{"id": ARTICLE_ID}]})
        if request.url.path.endswith("/consult/getArticle"):
            return httpx.Response(200, json={"article": {
                "id": ARTICLE_ID, "num": "L. 123-4",
                "nomCode": "Code général de la fonction publique",
                "texte": full_text,
            }})
        return httpx.Response(404)

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    results = await connector.search_code_articles(
        "article L. 123-4 rémunération indemnité", date(2026, 11, 24),
    )

    assert len(results) == 1
    assert len(results[0]["excerpt"]) <= 1800
    assert len(results[0]["analysis_excerpt"]) > 1800
    assert exception in results[0]["analysis_excerpt"]
    assert exception not in results[0]["excerpt"]
