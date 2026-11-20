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



@pytest.mark.asyncio
async def test_orchestrator_uses_only_consulted_cetat_full_text_when_feature_enabled(monkeypatch):
    import json
    import app.orchestrator as module
    from app.orchestrator import LegalOrchestrator
    from app.schemas import AskRequest

    monkeypatch.setattr(settings, "legifrance_cetat_fulltext_enabled", True)
    monkeypatch.setattr(type(module.legifrance), "configured", property(lambda self: True))

    async def fake_token(self):
        return "test-token"

    async def no_code_articles(*args, **kwargs):
        return []

    regulatory_text = (
        "Le décret relatif aux indemnités horaires pour travaux supplémentaires "
        "définit les conditions de versement applicables aux agents territoriaux. "
    ) * 3

    async def regulatory_texts(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000012345678",
            "title": "Décret n° 2002-60 relatif aux indemnités horaires pour travaux supplémentaires",
            "document_kind": "DECREE",
            "official_number": "2002-60",
            "full_text": regulatory_text,
        }]

    decision_id = "CETATEXT000012345678"
    decision_text = (
        "Le Conseil d'État examine la situation d'un agent territorial d'une commune "
        "au regard des indemnités horaires pour travaux supplémentaires et des règles "
        "applicables à la fonction publique territoriale. "
    ) * 4

    async def case_search(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_CETAT_SEARCH",
            "source_id": decision_id,
            "title": "Décision concernant un agent territorial",
            "decision_date": "2024-05-10",
            "text": "Extrait de recherche non probant.",
            "full_text_retrieved": False,
        }]

    async def case_consult(source_id):
        assert source_id == decision_id
        return {
            "source_type": "LEGIFRANCE_CETAT_FULL_TEXT",
            "source_id": decision_id,
            "title": "Décision concernant un agent territorial",
            "decision_date": "2024-05-10",
            "case_number": "123456",
            "jurisdiction": "Conseil d'État",
            "text": decision_text,
            "full_text_retrieved": True,
            "official_source": True,
            "source_status": "OFFICIAL_FULL_TEXT_ID_MATCHED",
        }

    captured = {}

    async def fake_ai(**kwargs):
        captured["sources"] = kwargs["sources"]
        return json.dumps({"claims": []})

    async def provider_available():
        return {"status": "AVAILABLE"}

    monkeypatch.setattr(type(module.legifrance), "_get_token", fake_token)
    monkeypatch.setattr(module.legifrance, "search_code_articles", no_code_articles)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", regulatory_texts)
    monkeypatch.setattr(module.case_law_connector, "search", case_search)
    monkeypatch.setattr(module.case_law_connector, "consult", case_consult)
    monkeypatch.setattr(module, "analyze_question", fake_ai)
    monkeypatch.setattr(module, "check_provider_availability", provider_available)

    await LegalOrchestrator().ask(
        AskRequest(
            employer="NATIONAL",
            facts_date="2025-01-01",
            question="On ne me paie pas mes heures supplémentaires.",
        ),
        organization_id="00000000-0000-0000-0000-000000000001",
    )

    ai_sources = captured["sources"]
    assert any(
        source.get("source_type") == "LEGIFRANCE_CETAT_FULL_TEXT"
        and source.get("source_id") == decision_id
        and source.get("content_kind") == "FULL_TEXT"
        and source.get("citation_integrity", {}).get("valid") is True
        for source in ai_sources
    )
    assert not any(
        source.get("source_type") == "LEGIFRANCE_CETAT_SEARCH"
        for source in ai_sources
    )


@pytest.mark.parametrize(
    ("decision_date", "requested_date", "expected"),
    [
        ("2024-05-10", date(2025, 1, 1), "DECISION_AVAILABLE_BY_REQUESTED_DATE"),
        ("2025-02-01", date(2025, 1, 1), "DECISION_POSTERIOR_TO_REQUESTED_DATE"),
        (None, date(2025, 1, 1), "TEMPORAL_SCOPE_INCOMPLETE"),
        ("date inconnue", date(2025, 1, 1), "TEMPORAL_SCOPE_INCOMPLETE"),
    ],
)
def test_decision_temporal_status_requires_a_verified_date(decision_date, requested_date, expected):
    from app.jurisprudence import decision_temporal_status
    assert decision_temporal_status(decision_date, requested_date) == expected



def test_cetat_results_are_interleaved_across_research_axes_and_deduplicated():
    from app.jurisprudence import interleave_case_law_results
    first = [
        {"source_id": "CETATEXT000000000001", "title": "A1"},
        {"source_id": "CETATEXT000000000002", "title": "A2"},
    ]
    second = [
        {"source_id": "CETATEXT000000000001", "title": "duplicate"},
        {"source_id": "CETATEXT000000000003", "title": "B2"},
    ]
    third = [{"source_id": "CETATEXT000000000004", "title": "C1"}]
    selected = interleave_case_law_results([first, second, third], limit=3)
    assert [item["source_id"] for item in selected] == [
        "CETATEXT000000000001", "CETATEXT000000000004", "CETATEXT000000000002"
    ]




def test_parse_administrative_open_data_zip_imports_only_relevant_full_text():
    from io import BytesIO
    import zipfile
    from app.legal_ingestion import parse_administrative_open_data_zip

    xml = b"""<Decision>
      <Identification>DTA_2024001_20240510.xml</Identification>
      <Code_Juridiction>TA38</Code_Juridiction>
      <Nom_Juridiction>Tribunal administratif de Grenoble</Nom_Juridiction>
      <Numero_Dossier>2400001</Numero_Dossier>
      <Date_Lecture>2024-05-10</Date_Lecture>
      <Numero_ECLI>ECLI:FR:TA38:2024:2400001</Numero_ECLI>
      <Code_Publication>C</Code_Publication>
      <Type_Decision>décision</Type_Decision>
      <Texte_Integral><p>La commune a recruté un agent contractuel territorial et a pris une décision relative à sa rémunération. Le tribunal examine les règles applicables à cet agent public territorial et les garanties qui lui sont dues.</p></Texte_Integral>
    </Decision>"""
    archive_bytes = BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("DTA_2024001_20240510.xml", xml)
    items = parse_administrative_open_data_zip(archive_bytes.getvalue(), "TA_202405.zip")
    assert len(items) == 1
    item = items[0]
    assert item["source_type"] == "OTHER_OFFICIAL"
    assert item["document_kind"] == "ADMIN_CASELAW"
    assert item["source_status"] == "OFFICIAL_XML_IMPORTED"
    assert item["signature_date"] == date(2024, 5, 10)
    assert item["official_number"] == "2400001"
    assert "agent contractuel territorial" in item["full_text"]
    assert item["raw_metadata"]["publication_code"] == "C"


def test_parse_administrative_open_data_zip_rejects_invalid_archive():
    from app.legal_ingestion import parse_administrative_open_data_zip
    with pytest.raises(ValueError, match="ZIP valide"):
        parse_administrative_open_data_zip(b"not a zip", "broken.zip")
