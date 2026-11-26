from datetime import date
import httpx
import pytest

from app.config import settings
from app.legifrance import LegifranceConnector
from app.jurisprudence import AdministrativeCaseLawConnector


@pytest.mark.asyncio
async def test_piste_oauth_rejection_reports_only_allowlisted_error_code(monkeypatch):
    from app.legifrance import LegifranceUnavailable

    monkeypatch.setattr(settings, "legifrance_client_id", "test-client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "test-secret")
    monkeypatch.setattr(settings, "legifrance_scope", "openid")

    def handler(request):
        assert request.url.path == "/api/oauth/token"
        assert request.headers["content-type"].startswith("application/x-www-form-urlencoded")
        body = request.content.decode("utf-8")
        assert "grant_type=client_credentials" in body
        assert "client_id=test-client" in body
        assert "client_secret=test-secret" in body
        return httpx.Response(400, json={
            "error": "invalid_client",
            "error_description": "Do not expose this description or the supplied secret.",
        })

    connector = LegifranceConnector(transport=httpx.MockTransport(handler))
    with pytest.raises(LegifranceUnavailable, match="HTTP 400, code invalid_client") as error:
        await connector._get_token()
    assert "test-secret" not in str(error.value)
    assert "Do not expose" not in str(error.value)


def test_piste_oauth_error_code_rejects_untrusted_provider_text():
    from app.legifrance import _safe_piste_oauth_error_code

    assert _safe_piste_oauth_error_code(
        httpx.Response(400, json={"error": "invalid_scope"})
    ) == "invalid_scope"
    assert _safe_piste_oauth_error_code(
        httpx.Response(400, json={"error": "invalid_client: secret=leak"})
    ) is None
    assert _safe_piste_oauth_error_code(
        httpx.Response(400, json={"error_description": "invalid_client"})
    ) is None


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
    monkeypatch.setattr(module, "_france_today", lambda: date(2026, 11, 21))
    monkeypatch.setattr(type(module.legifrance), "configured", property(lambda self: True))

    async def fake_token(self):
        return "test-token"

    captured_dates = {"code": [], "regulatory": [], "case_law": []}

    async def no_code_articles(*args, **kwargs):
        captured_dates["code"].append(args[1])
        text = (
            "Le Code général de la fonction publique encadre les droits des agents publics "
            "territoriaux et les indemnités horaires pour travaux supplémentaires. "
        ) * 3
        return [{
            "source_type": "LEGIFRANCE_API",
            "source_id": "LEGIARTI000012345679",
            "article": "L123-4",
            "title": "Code général de la fonction publique — heures supplémentaires",
            "text": text,
        }]

    regulatory_text = (
        "Le décret relatif aux indemnités horaires pour travaux supplémentaires "
        "définit les conditions de versement applicables aux agents territoriaux. "
    ) * 3

    async def regulatory_texts(*args, **kwargs):
        captured_dates["regulatory"].append(args[1])
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
        captured_dates["case_law"].append(args[1])
        return [{
            "source_type": "LEGIFRANCE_CETAT_SEARCH",
            "source_id": decision_id,
            "title": "Décision concernant un agent territorial",
            "decision_date": "2025-02-10",
            "text": "Extrait de recherche non probant.",
            "full_text_retrieved": False,
        }]

    async def case_consult(source_id):
        assert source_id == decision_id
        return {
            "source_type": "LEGIFRANCE_CETAT_FULL_TEXT",
            "source_id": decision_id,
            "title": "Décision concernant un agent territorial",
            "decision_date": "2025-02-10",
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

    # A past facts date triggers both the historical legal-text lookup and
    # the current-law lookup. Case law is searched through today, not cut off
    # at the date of the incident.
    assert date(2025, 1, 1) in captured_dates["code"]
    assert date(2026, 11, 21) in captured_dates["code"]
    assert date(2025, 1, 1) in captured_dates["regulatory"]
    assert date(2026, 11, 21) in captured_dates["regulatory"]
    assert captured_dates["case_law"]
    assert set(captured_dates["case_law"]) == {date(2026, 11, 21)}

    ai_sources = captured["sources"]
    assert any(
        source.get("source_type") == "LEGIFRANCE_API"
        and source.get("version_role") == "FACTS_DATE_VERSION"
        for source in ai_sources
    )
    assert any(
        source.get("source_type") == "LEGIFRANCE_API"
        and source.get("version_role") == "CURRENT_LAW_VERSION"
        for source in ai_sources
    )
    assert any(
        source.get("source_type") == "LEGIFRANCE_CETAT_FULL_TEXT"
        and source.get("source_id") == decision_id
        and source.get("content_kind") == "FULL_TEXT"
        and source.get("citation_integrity", {}).get("valid") is True
        and source.get("temporal_status") == "DECISION_POSTERIOR_TO_FACTS"
        for source in ai_sources
    )
    assert not any(
        source.get("source_type") == "LEGIFRANCE_CETAT_SEARCH"
        for source in ai_sources
    )


@pytest.mark.parametrize(
    ("decision_date", "requested_date", "expected"),
    [
        ("2024-05-10", date(2025, 1, 1), "DECISION_ANTERIOR_OR_CONTEMPORANEOUS_TO_FACTS"),
        ("2025-02-01", date(2025, 1, 1), "DECISION_POSTERIOR_TO_FACTS"),
        (None, date(2025, 1, 1), "DECISION_DATE_UNKNOWN"),
        ("date inconnue", date(2025, 1, 1), "DECISION_DATE_UNKNOWN"),
        ("2025-02-01", None, "DECISION_DATE_VERIFIED_NO_FACTS_DATE"),
    ],
)
def test_decision_temporal_status_classifies_timing_without_excluding_later_case_law(decision_date, requested_date, expected):
    from app.jurisprudence import decision_temporal_status
    assert decision_temporal_status(decision_date, requested_date) == expected



def test_undated_personal_case_is_not_misclassified_as_general_information():
    from app.orchestrator import _analysis_mode, classify_question_intent

    personal = classify_question_intent("Mon employeur m'a refusé mon congé.")
    general = classify_question_intent("Quels sont les droits à congé des agents territoriaux ?")
    assert personal == "PERSONAL_CASE"
    assert general == "GENERAL_INFORMATION"
    assert _analysis_mode(personal, False) == "PERSONAL_CASE_WITHOUT_FACTS_DATE"
    assert _analysis_mode(general, False) == "GENERAL_CURRENT_LAW_WITHOUT_FACTS_DATE"
    assert _analysis_mode(personal, True) == "CASE_SPECIFIC"


def test_permanent_legal_version_is_checked_against_historical_facts_date():
    from app.orchestrator import _permanent_source_temporal_metadata

    item = {
        "document_kind": "CODE",
        "requested_date": date(2026, 11, 24),
        "valid_from": date(2020, 1, 1),
        "valid_to": date(2024, 12, 31),
        "version_status": "REPEALED",
        "temporal_status": "NO_LONGER_IN_FORCE",
    }
    status, explanation = _permanent_source_temporal_metadata(item, date(2024, 6, 1))
    assert status == "IN_FORCE_ON_FACTS_DATE"
    assert explanation and "couvrent le 2024-06-01" in explanation


def test_permanent_legal_version_is_rejected_outside_its_validity_period():
    from app.orchestrator import _permanent_source_temporal_metadata

    item = {
        "document_kind": "LAW",
        "requested_date": date(2026, 11, 24),
        "valid_from": date(2025, 1, 1),
        "valid_to": date(2025, 12, 31),
        "temporal_status": "NO_LONGER_IN_FORCE",
    }
    before, _ = _permanent_source_temporal_metadata(item, date(2024, 12, 31))
    after, _ = _permanent_source_temporal_metadata(item, date(2026, 1, 1))
    assert before == "NOT_YET_EFFECTIVE"
    assert after == "NO_LONGER_IN_FORCE"


def test_permanent_legal_version_with_missing_historical_bounds_is_not_assumed_applicable():
    from app.orchestrator import _permanent_source_temporal_metadata

    item = {
        "document_kind": "CODE",
        "requested_date": date(2026, 11, 24),
        "valid_from": None,
        "valid_to": None,
        "temporal_status": "IN_FORCE_ON_REQUESTED_DATE",
    }
    status, explanation = _permanent_source_temporal_metadata(item, date(2024, 6, 1))
    assert status == "TEMPORAL_SCOPE_INCOMPLETE"
    assert explanation and "ne permettent pas de vérifier" in explanation


def test_historical_in_force_corpus_version_passes_final_orchestrator_source_gate():
    from app.orchestrator import _is_usable_permanent_source

    source = {
        "source_id": "CORPUS_VERSION_HISTORICAL",
        "content_kind": "FULL_TEXT",
        "citation_integrity": {"valid": True},
        "temporal_status": "IN_FORCE_ON_FACTS_DATE",
        "analysis_eligible": True,
        "claim_eligible": True,
        "research_axis_relevant": True,
    }
    assert _is_usable_permanent_source(source, {source["source_id"]}) is True
    source["temporal_status"] = "NO_LONGER_IN_FORCE"
    assert _is_usable_permanent_source(source, {source["source_id"]}) is False


def test_imported_administrative_case_law_after_facts_is_kept_as_interpretative():
    from app.orchestrator import _permanent_source_temporal_metadata

    item = {
        "document_kind": "ADMIN_CASELAW",
        "signature_date": date(2025, 2, 10),
        "temporal_status": "DECISION_AVAILABLE_BY_REQUESTED_DATE",
    }
    status, explanation = _permanent_source_temporal_metadata(item, date(2025, 1, 1))
    assert status == "DECISION_POSTERIOR_TO_FACTS"
    assert explanation and "peut éclairer l'interprétation" in explanation


def test_future_dated_imported_administrative_decision_is_rejected():
    from app.orchestrator import _permanent_source_temporal_metadata

    item = {
        "document_kind": "ADMIN_CASELAW",
        "signature_date": date(2027, 2, 10),
        "temporal_status": "DECISION_POSTERIOR_TO_REQUESTED_DATE",
    }
    status, explanation = _permanent_source_temporal_metadata(item, date(2025, 1, 1))
    assert status == "DECISION_AFTER_RETRIEVAL_DATE"
    assert explanation and "postérieure à la date de recherche" in explanation


def test_imported_administrative_case_law_without_facts_date_is_not_excluded():
    from app.orchestrator import _permanent_source_temporal_metadata

    item = {
        "document_kind": "ADMIN_CASELAW",
        "signature_date": date(2025, 2, 10),
        "temporal_status": "DECISION_AVAILABLE_BY_REQUESTED_DATE",
    }
    status, explanation = _permanent_source_temporal_metadata(item, None)
    assert status == "DECISION_DATE_VERIFIED_NO_FACTS_DATE"
    assert explanation is None


def test_permanent_case_law_decision_before_or_on_facts_date_passes_source_gate():
    from app.orchestrator import _is_usable_permanent_source

    source = {
        "source_id": "CORPUS_CASE_LAW_BEFORE_FACTS",
        "content_kind": "FULL_TEXT",
        "citation_integrity": {"valid": True},
        "analysis_eligible": True,
        "claim_eligible": True,
        "research_axis_relevant": True,
        "temporal_status": "DECISION_ANTERIOR_OR_CONTEMPORANEOUS_TO_FACTS",
    }
    assert _is_usable_permanent_source(source, {source["source_id"]}) is True


def test_permanent_case_law_with_verified_date_and_no_facts_date_passes_source_gate():
    from app.orchestrator import _is_usable_permanent_source

    source = {
        "source_id": "CORPUS_CASE_LAW_CURRENT_CONTEXT",
        "content_kind": "FULL_TEXT",
        "citation_integrity": {"valid": True},
        "analysis_eligible": True,
        "claim_eligible": True,
        "research_axis_relevant": True,
        "temporal_status": "DECISION_DATE_VERIFIED_NO_FACTS_DATE",
    }
    assert _is_usable_permanent_source(source, {source["source_id"]}) is True


def test_permanent_case_law_after_facts_remains_excluded_from_conclusive_source_gate():
    from app.orchestrator import _is_usable_permanent_source

    source = {
        "source_id": "CORPUS_CASE_LAW_AFTER_FACTS",
        "content_kind": "FULL_TEXT",
        "citation_integrity": {"valid": True},
        "analysis_eligible": True,
        "claim_eligible": True,
        "research_axis_relevant": True,
        "temporal_status": "DECISION_POSTERIOR_TO_FACTS",
    }
    assert _is_usable_permanent_source(source, {source["source_id"]}) is False


def test_period_analysis_keeps_later_case_law_and_endpoint_valid_local_documents():
    from app.orchestrator import _source_allowed_for_period_analysis

    start, end = date(2024, 1, 1), date(2024, 6, 30)
    later_decision = {
        "source_type": "LEGIFRANCE_CETAT_FULL_TEXT",
        "content_kind": "FULL_TEXT",
        "temporal_status": "DECISION_POSTERIOR_TO_FACTS",
    }
    imported_decision = {
        "source_type": "OTHER_OFFICIAL",
        "document_kind": "ADMIN_CASELAW",
        "content_kind": "FULL_TEXT",
        "temporal_status": "DECISION_POSTERIOR_TO_FACTS",
    }
    local_at_start = {
        "source_type": "LOCAL_DOCUMENT",
        "validation_status": "VERIFIED_HISTORICAL",
        "temporal_status": "VERIFIED_APPLICABLE",
        "version_endpoint": "START",
    }
    local_not_applicable = {
        **local_at_start,
        "temporal_status": "NOT_APPLICABLE_ON_REQUESTED_DATE",
    }
    assert _source_allowed_for_period_analysis(later_decision, True, start, end)
    assert _source_allowed_for_period_analysis(imported_decision, True, start, end)
    assert _source_allowed_for_period_analysis(local_at_start, True, start, end)
    one_endpoint_text = {
        "source_type": "LEGIFRANCE_API",
        "period_endpoint_match": True,
        "version_endpoint": "START",
    }
    assert _source_allowed_for_period_analysis(one_endpoint_text, True, start, end)
    one_endpoint_text["period_endpoint_match"] = False
    assert not _source_allowed_for_period_analysis(one_endpoint_text, True, start, end)
    assert not _source_allowed_for_period_analysis(local_not_applicable, True, start, end)
    historical_decree = {
        "source_type": "OTHER_OFFICIAL",
        "document_kind": "DECREE",
        "valid_from": "2024-01-01",
        "valid_to": "2024-12-31",
    }
    assert _source_allowed_for_period_analysis(historical_decree, True, start, end)


def test_local_document_search_checks_historical_and_current_reference_dates():
    from app.orchestrator import _local_document_reference_dates

    start = date(2024, 1, 1)
    end = date(2024, 6, 30)
    today = date(2026, 11, 21)
    assert _local_document_reference_dates(start, end, today) == [
        (start, "START"), (end, "END"), (today, "CURRENT"),
    ]
    assert _local_document_reference_dates(None, None, today) == [(today, "CURRENT")]


def test_ongoing_situation_uses_today_as_case_law_reference_date():
    from app.orchestrator import _case_law_reference_date

    today = date(2026, 11, 21)
    start = date(2024, 1, 1)
    assert _case_law_reference_date(start, None, True, today) == today
    assert _case_law_reference_date(start, date(2024, 6, 30), False, today) == date(2024, 6, 30)
    assert _case_law_reference_date(None, None, False, today) is None


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

    xml = """<Decision>
      <Identification>DTA_2024001_20240510.xml</Identification>
      <Code_Juridiction>TA38</Code_Juridiction>
      <Nom_Juridiction>Tribunal administratif de Grenoble</Nom_Juridiction>
      <Numero_Dossier>2400001</Numero_Dossier>
      <Date_Lecture>2024-05-10</Date_Lecture>
      <Numero_ECLI>ECLI:FR:TA38:2024:2400001</Numero_ECLI>
      <Code_Publication>C</Code_Publication>
      <Type_Decision>décision</Type_Decision>
      <Solution>Rejet pour irrecevabilité</Solution>
      <Texte_Integral><p>La commune a recruté un agent contractuel territorial et a pris une décision relative à sa rémunération. Le tribunal examine les règles applicables à cet agent public territorial et les garanties qui lui sont dues.</p></Texte_Integral>
    </Decision>""".encode("utf-8")
    archive_bytes = BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("DTA_2024001_20240510.xml_TA38", xml)
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
    assert item["raw_metadata"]["solution"] == "Rejet pour irrecevabilité"
    assert item["raw_metadata"]["source_license"] == "Licence Ouverte version 2.0"
    assert len(item["raw_metadata"]["source_xml_sha256"]) == 64
    assert item["jurisdiction"] == "Tribunal administratif de Grenoble"
    assert item["raw_metadata"]["court_seat"] == "Grenoble"


def test_parse_administrative_open_data_zip_rejects_invalid_archive():
    from app.legal_ingestion import parse_administrative_open_data_zip
    with pytest.raises(ValueError, match="ZIP valide"):
        parse_administrative_open_data_zip(b"not a zip", "broken.zip")



def test_open_data_search_results_mark_only_relevance_selected_passages():
    from app.legal_corpus import search_legal_corpus
    import inspect
    source = inspect.getsource(search_legal_corpus)
    assert "RELEVANCE_SELECTED_PASSAGES_FROM_HASH_VERIFIED_FULL_TEXT" in source



def test_administrative_open_data_import_includes_explicit_state_public_service_decisions():
    from io import BytesIO
    import zipfile
    from app.legal_ingestion import parse_administrative_open_data_zip

    xml = """<Decision>
      <Identification>CE_2024002_20240510.xml</Identification>
      <Code_Juridiction>CE</Code_Juridiction>
      <Nom_Juridiction>Section du Contentieux</Nom_Juridiction>
      <Numero_Dossier>2400002</Numero_Dossier>
      <Date_Lecture>2024-05-10</Date_Lecture>
      <Texte_Integral><p>Un agent de l'Etat affecté dans un ministère conteste une décision de rémunération prise par l'administration centrale au regard des règles propres à la fonction publique de l'Etat.</p></Texte_Integral>
    </Decision>""".encode("utf-8")
    archive_bytes = BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("CE_2024002_20240510.xml", xml)
    records = parse_administrative_open_data_zip(archive_bytes.getvalue(), "CE_202405.zip")
    assert len(records) == 1
    assert records[0]["raw_metadata"]["public_service_scope"] == "FPE"
    assert records[0]["jurisdiction"] == "Conseil d'État"
    assert records[0]["raw_metadata"]["court_name"] == "Conseil d'État"
    assert records[0]["raw_metadata"]["court_seat"] == "Paris"
    assert records[0]["raw_metadata"]["decision_section"] == "Section du Contentieux"


def test_administrative_open_data_import_rejects_xml_entity_declarations():
    from io import BytesIO
    import zipfile
    from app.legal_ingestion import parse_administrative_open_data_zip

    xml = b"<!DOCTYPE Decision [<!ENTITY xxe SYSTEM 'file:///etc/passwd'>]><Decision><Texte_Integral>&xxe;</Texte_Integral></Decision>"
    archive_bytes = BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("malicious.xml", xml)
    assert parse_administrative_open_data_zip(archive_bytes.getvalue(), "malicious.zip") == []



def test_legal_corpus_results_are_interleaved_across_subquestions():
    from app.legal_corpus import interleave_legal_corpus_results
    first = [
        {"source_id": "OPEN_DATA_JA_0001", "title": "A1"},
        {"source_id": "OPEN_DATA_JA_0002", "title": "A2"},
    ]
    second = [
        {"source_id": "OPEN_DATA_JA_0001", "title": "duplicate"},
        {"source_id": "OPEN_DATA_JA_0003", "title": "B2"},
    ]
    third = [{"source_id": "OPEN_DATA_JA_0004", "title": "C1"}]
    selected = interleave_legal_corpus_results([first, second, third], limit=3)
    assert [item["source_id"] for item in selected] == [
        "OPEN_DATA_JA_0001", "OPEN_DATA_JA_0004", "OPEN_DATA_JA_0002"
    ]


@pytest.mark.asyncio
async def test_consult_rejects_truncated_oversized_decision_text(monkeypatch):
    monkeypatch.setattr(settings, "legifrance_client_id", "client")
    monkeypatch.setattr(settings, "legifrance_client_secret", "secret")
    oversized = "Texte intégral officiel. " * 6000
    def handler(request):
        if request.url.path.endswith("/api/oauth/token"):
            return httpx.Response(200, json={"access_token": "token", "expires_in": 3600})
        return httpx.Response(200, json={"text": {
            "id": "CETATEXT000012345678", "texte": oversized,
        }})
    connector = AdministrativeCaseLawConnector(LegifranceConnector(transport=httpx.MockTransport(handler)))
    with pytest.raises(Exception, match="texte intégral vérifiable"):
        await connector.consult("CETATEXT000012345678")

def test_open_data_case_law_filter_excludes_local_authority_cases_unrelated_to_staff():
    from app.legal_ingestion import _is_fpt_employment_case_law

    urban_planning = (
        "La commune a approuvé le plan local d'urbanisme au regard du code "
        "général des collectivités territoriales."
    )
    procurement = (
        "La commune demande le paiement du solde d'un marché public. "
        "Le litige porte sur les obligations contractuelles et la rémunération "
        "du titulaire du marché."
    )
    elected_officials = (
        "Le maire refuse de justifier le versement d'une indemnité de fonction "
        "aux élus municipaux et aux conseillers municipaux."
    )
    assert not _is_fpt_employment_case_law(
        "Décision concernant une commune", urban_planning,
        {"scope": "FPT", "analysis_eligible": True},
    )
    # "Contractuel" and "rémunération" in a public contract do not mean
    # contractual employment in the territorial civil service.
    assert not _is_fpt_employment_case_law(
        "Marché public conclu par une commune", procurement,
        {"scope": "FPT", "analysis_eligible": True},
    )
    assert not _is_fpt_employment_case_law(
        "Décision concernant une commune", elected_officials,
        {"scope": "FPT", "analysis_eligible": True},
    )


def test_open_data_case_law_filter_keeps_local_authority_hr_disputes():
    from app.legal_ingestion import _is_fpt_employment_case_law

    harassment_case = (
        "Mme B sollicite le tribunal après des faits de harcèlement et une "
        "demande de protection fonctionnelle auprès du service des ressources "
        "humaines de la commune de Sarcelles."
    )
    assert _is_fpt_employment_case_law(
        "Décision concernant la commune de Sarcelles", harassment_case,
        {"scope": "OUT_OF_SCOPE_OR_UNCONFIRMED", "analysis_eligible": False},
    )



def test_administrative_open_data_import_accepts_explicit_hospital_employment_decisions():
    from io import BytesIO
    import zipfile
    from app.legal_ingestion import parse_administrative_open_data_zip

    xml = """<Decision>
      <Identification>TA_2024003_20240512.xml</Identification>
      <Code_Juridiction>TA69</Code_Juridiction>
      <Nom_Juridiction>Tribunal administratif de Lyon</Nom_Juridiction>
      <Numero_Dossier>2400003</Numero_Dossier>
      <Date_Lecture>2024-05-12</Date_Lecture>
      <Texte_Integral><p>Un agent hospitalier d'un établissement public de santé conteste une décision relative à son accident de service au regard des règles propres à la fonction publique hospitalière.</p></Texte_Integral>
    </Decision>""".encode("utf-8")
    archive_bytes = BytesIO()
    with zipfile.ZipFile(archive_bytes, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("TA_2024003_20240512.xml", xml)
    records = parse_administrative_open_data_zip(archive_bytes.getvalue(), "TA_202405.zip")
    assert len(records) == 1
    assert records[0]["raw_metadata"]["public_service_scope"] == "FPH"


def test_open_data_import_rejects_mixed_branch_decisions_even_with_local_employer_context():
    from app.legal_ingestion import _public_service_employment_case_law_scope

    title = "Décision relative à la fonction publique territoriale et à la fonction publique hospitalière"
    body = (
        "La commune a pris une décision disciplinaire concernant un agent territorial "
        "et un agent hospitalier. Le litige porte sur les garanties disciplinaires."
    )
    assert _public_service_employment_case_law_scope(title, body) is None

def test_verified_admin_open_data_scope_uses_full_decision_ingestion_classification():
    from app.orchestrator import _classify_permanent_source_scope

    source = {
        "source_type": "OTHER_OFFICIAL",
        "document_kind": "ADMIN_CASELAW",
        "source_status": "OFFICIAL_XML_IMPORTED",
        # The retrieved passage itself need not repeat the branch marker.
        "title": "Temps de travail",
        "excerpt": "Le litige porte sur l'organisation du temps de travail.",
        "raw_metadata": {
            "import_method": "JUSTICE_ADMINISTRATIVE_OPEN_DATA_XML",
            "public_service_scope": "FPT",
            "scope_evidence": ["agents territoriaux"],
        },
    }
    fpt = _classify_permanent_source_scope(source, "FPT")
    assert fpt["scope"] == "FPT"
    assert fpt["analysis_eligible"] is True
    assert fpt["claim_eligible"] is True

    fpe = _classify_permanent_source_scope(source, "FPE")
    assert fpe["scope"] == "FPT"
    assert fpe["analysis_eligible"] is False
    assert fpe["claim_eligible"] is False


def test_unverified_admin_scope_metadata_is_not_trusted():
    from app.orchestrator import _classify_permanent_source_scope

    source = {
        "source_type": "OTHER_OFFICIAL",
        "document_kind": "ADMIN_CASELAW",
        "source_status": "IMPORTED_UNVERIFIED",
        "title": "Temps de travail",
        "excerpt": "Le litige porte sur l'organisation du temps de travail.",
        "raw_metadata": {
            "import_method": "JUSTICE_ADMINISTRATIVE_OPEN_DATA_XML",
            "public_service_scope": "FPT",
            "scope_evidence": ["agents territoriaux"],
        },
    }
    result = _classify_permanent_source_scope(source, "FPT")
    assert result["scope"] != "FPT"
    assert result["analysis_eligible"] is False


def test_verified_admin_open_data_common_scope_applies_to_all_versants():
    from app.orchestrator import _classify_permanent_source_scope

    source = {
        "source_type": "OTHER_OFFICIAL",
        "document_kind": "ADMIN_CASELAW",
        "source_status": "OFFICIAL_XML_IMPORTED",
        "title": "Dispositions communes",
        "excerpt": "Le litige concerne les trois fonctions publiques.",
        "raw_metadata": {
            "import_method": "JUSTICE_ADMINISTRATIVE_OPEN_DATA_XML",
            "public_service_scope": "COMMON_PUBLIC_SERVICE",
            "scope_evidence": ["agents des trois versants"],
        },
    }
    for versant in ("FPT", "FPE", "FPH"):
        result = _classify_permanent_source_scope(source, versant)
        assert result["scope"] == "COMMON_PUBLIC_SERVICE"
        assert result["analysis_eligible"] is True
        assert result["claim_eligible"] is True
