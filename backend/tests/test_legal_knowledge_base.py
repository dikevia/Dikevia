from datetime import date
import pytest

from app.legal_corpus import clean_text, sha256_text, split_text, temporal_status, safe_official_url, expand_legal_query
from app.legal_ingestion import parse_circulaires_xml
from app.legifrance import LegifranceConnector


def test_split_text_keeps_all_text_and_overlap():
    text = ("A paragraph.\n" * 900).strip()
    chunks = split_text(text, size=1000, overlap=100)
    assert len(chunks) > 1
    assert all(chunks)
    assert chunks[0][-100:] in chunks[1]


def test_clean_text_and_hash_are_deterministic():
    assert clean_text("<p>Bonjour&nbsp;monde</p>") == "Bonjour monde"
    assert sha256_text("juris") == sha256_text("juris")
    assert sha256_text("juris") != sha256_text("JURIS")


def test_temporal_status_is_conservative_when_dates_missing():
    requested = date(2025, 1, 1)
    assert temporal_status(date(2024, 1, 1), date(2025, 1, 1), requested) == "IN_FORCE_ON_REQUESTED_DATE"
    assert temporal_status(date(2025, 2, 1), None, requested) == "NOT_YET_EFFECTIVE"
    assert temporal_status(None, None, requested) == "TEMPORAL_SCOPE_INCOMPLETE"
    assert temporal_status(None, None, requested, "ADMIN_CASELAW", date(2024, 6, 1)) == "DECISION_AVAILABLE_BY_REQUESTED_DATE"
    assert temporal_status(None, None, requested, "ADMIN_CASELAW", date(2025, 6, 1)) == "DECISION_POSTERIOR_TO_REQUESTED_DATE"
    assert temporal_status(None, None, requested, "DECREE", raw_payload={"requested_date": "2025-01-01"}, version_status="IN_FORCE") == "IN_FORCE_ON_REQUESTED_DATE"
    assert temporal_status(None, None, requested, "DECREE", raw_payload='{"requested_date":"2025-01-01"}', version_status="IN_FORCE") == "IN_FORCE_ON_REQUESTED_DATE"


def test_only_allowlisted_public_legal_and_institutional_source_urls_are_kept():
    assert safe_official_url("https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000000")
    assert safe_official_url("https://opendata.justice-administrative.fr/")
    assert safe_official_url("https://www.service-public.gouv.fr/particuliers/vosdroits/F123")
    assert safe_official_url("https://www.data.gouv.fr/datasets/example")
    assert safe_official_url("https://www.fonction-publique.gouv.fr/")
    assert safe_official_url("https://www.collectivites-locales.gouv.fr/")
    assert safe_official_url("https://www.cnfpt.fr/")
    assert safe_official_url("https://wikiterritorial.cnfpt.fr/")
    assert safe_official_url("https://info.gouv.fr/")
    assert safe_official_url("https://www.cdg35.fr/")
    assert safe_official_url("https://www.cdg44.fr/")
    assert safe_official_url("https://www.cdg59.fr/")
    assert safe_official_url("https://www.cdg69.fr/")
    assert safe_official_url("https://www.cig929394.fr/")
    assert safe_official_url("https://www.cdg35.bzh/")
    assert safe_official_url("https://uffa.cfdt.fr/")
    assert safe_official_url("https://www.cfdt-interco31.fr/")
    assert safe_official_url("https://cfdtinterco35.fr/")
    assert safe_official_url("https://www.cgtservicespublics.fr/")
    assert safe_official_url("https://www.fo-fonctionnaires.fr/")
    assert safe_official_url("https://www.cftc.fr/")
    assert safe_official_url("https://ledecodeur.cftc.fr/")
    assert safe_official_url("https://www.unsa-fp.org/")
    assert safe_official_url("https://fonctionpublique.solidaires.org/")
    assert safe_official_url("https://evil.example/legifrance") is None
    assert safe_official_url("https://service-public.gouv.fr.evil.example/") is None
    assert safe_official_url("https://cdg59.fr.evil.example/") is None
    assert safe_official_url("https://user@www.cnfpt.fr/") is None
    assert safe_official_url("https://www.cnfpt.fr:8443/") is None
    assert safe_official_url("http://legifrance.gouv.fr") is None


def test_parse_dila_circular_metadata_and_optional_body():
    xml = b'''<?xml version="1.0" encoding="UTF-8"?>
    <CIRCULAIRES><CIRCULAIRE><ID>circulaire-2026-001</ID>
    <TITRE>Organisation du temps de travail</TITRE><NOR>TFPF2600001C</NOR>
    <DATE_SIGNATURE>2026-02-01</DATE_SIGNATURE>
    <URL>https://www.legifrance.gouv.fr/circulaire/id/123</URL>
    </CIRCULAIRE></CIRCULAIRES>'''
    items = parse_circulaires_xml(xml)
    assert len(items) == 1
    assert items[0]["source_type"] == "DILA_CIRCULAIRES"
    assert items[0]["official_number"] == "TFPF2600001C"
    assert items[0]["source_status"] == "IMPORTED_UNVERIFIED"
    assert items[0]["full_text"] == ""
    assert items[0]["valid_from"] is None


def test_parse_dila_rejects_doctype():
    with pytest.raises(ValueError):
        parse_circulaires_xml(b'<!DOCTYPE x [<!ENTITY y "z">]><x/>')


@pytest.mark.asyncio
async def test_loda_search_uses_official_search_then_consult_workflow(monkeypatch):
    connector = LegifranceConnector()
    calls = []

    async def fake_request(method, path, *, json_body=None):
        calls.append((path, json_body))
        if path == "/search":
            return {"results": [{"id": "LEGITEXT000000000001", "titre": "Décret relatif à la FPT",
                "nor": "TFPF2600001D", "etat": "VIGUEUR", "dateDebut": "2024-01-01", "dateFin": "2027-01-01"}]}
        return {"text": {"id": "LEGITEXT000000000001", "texte": "<p>Texte officiel complet du décret relatif à la fonction publique territoriale et aux agents territoriaux de la fonction publique.</p>"}}

    monkeypatch.setattr(connector, "_request", fake_request)
    results = await connector.search_regulatory_texts("fonction publique territoriale", date(2026, 1, 1), 5)
    assert len(results) == 1
    assert results[0]["source_id"] == "LEGITEXT000000000001"
    assert results[0]["source_status"] == "OFFICIAL_TEXT_ID_VERIFIED"
    assert results[0]["full_text"].startswith("Texte officiel")
    assert calls[0][0] == "/search"
    assert calls[0][1]["fond"] == "LODA_DATE"
    assert calls[0][1]["recherche"]["filtres"][0]["facette"] == "DATE_VERSION"
    assert calls[1][0] == "/consult/legiPart"
    assert calls[1][1]["textId"] == "LEGITEXT000000000001"
    assert calls[1][1]["date"] == connector._date_epoch_ms(date(2026, 1, 1))

@pytest.mark.asyncio
async def test_upsert_persists_text_as_fulltext_chunks_and_hash():
    from uuid import uuid4
    from app.legal_corpus import upsert_legal_document

    class FakeConn:
        def __init__(self):
            self.calls = []
        async def fetchrow(self, query, *args):
            self.calls.append((query, args))
            return {"id": uuid4()}
        async def execute(self, query, *args):
            self.calls.append((query, args))

    conn = FakeConn()
    result = await upsert_legal_document(conn, {
        "source_type": "LEGIFRANCE_LODA", "source_id": "LEGITEXT000000000001",
        "title": "Décret test", "document_kind": "DECREE",
        "official_url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000001",
        "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
        "full_text": "Texte intégral officiel de test. " * 10,
        "valid_from": date(2024, 1, 1), "valid_to": date(2027, 1, 1),
        "version_key": "v2024", "version_status": "IN_FORCE",
    })
    assert result["text_imported"] is True
    assert result["chunks"] >= 1
    assert any("INSERT INTO legal_chunks" in call[0] and "FULL_TEXT" in call[0] for call in conn.calls)


@pytest.mark.asyncio
async def test_search_marks_unknown_temporal_range_as_incomplete():
    from app.legal_corpus import search_legal_corpus
    full_text = "Texte intégral officiel conservé et contrôlé par son empreinte SHA-256."
    class FakeConn:
        query = ""
        async def fetch(self, sql, *args):
            self.query = sql
            return [{"document_id": "d", "version_id": "v", "source_type": "LEGIFRANCE_LODA",
                "source_id": "LEGITEXT000000000001", "title": "Décret test", "document_kind": "DECREE",
                "official_number": "2024-100", "jurisdiction": None,
                "official_url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000001",
                "signature_date": None, "publication_date": None, "document_status": "UNKNOWN",
                "source_status": "OFFICIAL_TEXT_ID_VERIFIED", "raw_metadata": '{"publication_code":"B"}',
                "valid_from": None, "valid_to": None,
                "version_status": "UNKNOWN", "full_text": full_text,
                "text_sha256": sha256_text(full_text), "anchor": None, "content": full_text,
                "content_kind": "FULL_TEXT", "rank": 0.5}]
    conn = FakeConn()
    result = await search_legal_corpus(conn, "decret fonction publique", date(2026, 1, 1))
    assert "c.content_kind='FULL_TEXT'" in conn.query
    assert result[0]["temporal_status"] == "TEMPORAL_SCOPE_INCOMPLETE"
    assert result[0]["citation_integrity"]["text_hash_verified"] is True
    assert result[0]["citation_integrity"]["valid"] is True
    assert result[0]["raw_metadata"]["publication_code"] == "B"


def test_ai_authority_references_must_exist_in_retrieved_sources():
    from app.ai_provider import answer_references_are_grounded
    assert answer_references_are_grounded("Le décret n° 2024-100 est pertinent.", set(), {"2024-100"})
    assert not answer_references_are_grounded("Le décret n° 2024-999 est pertinent.", set(), {"2024-100"})


def test_production_requires_distinct_ingestion_database_role():
    from app.config import Settings, validate_runtime_configuration
    base = dict(app_env="production", database_url="postgresql://cfdt_juris_app:app@db/cfdt_juris",
        oidc_issuer="https://id.example", oidc_audience="cfdt-juris-api",
        oidc_jwks_url="https://id.example/jwks", cors_origins="https://juris.example",
        aws_endpoint_url_s3="https://storage.example", aws_region="us-east-2",
        aws_access_key_id="test-access", aws_secret_access_key="test-secret",
        document_storage_bucket="cfdt-juris-documents",
        platform_admin_database_url="postgresql://cfdt_juris_platform_admin:platform@db/cfdt_juris")
    with pytest.raises(RuntimeError, match="LEGAL_CORPUS_INGEST_DATABASE_URL"):
        validate_runtime_configuration(Settings(**base))
    with pytest.raises(RuntimeError, match="rôle PostgreSQL dédié"):
        validate_runtime_configuration(Settings(**base,
            legal_corpus_ingest_database_url="postgresql://cfdt_juris_app:app@db/cfdt_juris"))
    validate_runtime_configuration(Settings(**base,
        legal_corpus_ingest_database_url="postgresql://cfdt_juris_ingest:ingest@db/cfdt_juris"))



@pytest.mark.asyncio
async def test_loda_consult_rejects_mismatched_identifier_and_short_text():
    connector = LegifranceConnector()

    async def fake_request(method, path, *, json_body=None):
        if path == "/search":
            return {"results": [{"id": "LEGITEXT000000000001", "titre": "Décret test"}]}
        return {"text": {
            "id": "LEGITEXT000000000002",
            "texte": "Texte trop court."
        }}

    connector._request = fake_request
    assert await connector.search_regulatory_texts(
        "décret fonction publique", date(2024, 1, 1), limit=3
    ) == []



@pytest.mark.asyncio
async def test_loda_date_filtered_consult_preserves_unknown_status_and_marks_retrieved_version():
    connector = LegifranceConnector()

    async def fake_request(method, path, *, json_body=None):
        if path == "/search":
            return {"results": [{"id": "LEGITEXT000000000099", "titre": "Décret de test"}]}
        return {"text": {
            "id": "LEGITEXT000000000099",
            "texte": "Texte officiel du décret applicable à la date demandée. " * 4,
        }}

    connector._request = fake_request
    result = await connector.search_regulatory_texts(
        "décret fonction publique", date(2024, 6, 1), limit=3
    )
    assert len(result) == 1
    assert result[0]["status"] == "UNKNOWN"
    assert result[0]["version_status"] == "UNKNOWN"
    assert result[0]["raw_version_payload"]["date_filter"] == "DATE_VERSION"
    assert temporal_status(
        result[0]["valid_from"], result[0]["valid_to"], date(2024, 6, 1),
        document_kind=result[0]["document_kind"],
        signature_date=result[0]["signature_date"],
        raw_payload=result[0]["raw_version_payload"],
        version_status=result[0]["version_status"],
    ) == "VERSION_RETRIEVED_AT_REQUESTED_DATE"
    assert result[0]["raw_version_payload"]["matching_consulted_id"] == "LEGITEXT000000000099"


def test_legal_query_expansion_preserves_original_and_adds_fpt_terms():
    expanded = expand_legal_query("Je ne suis pas payé pour mes heures supplémentaires")
    assert expanded[0] == "Je ne suis pas payé pour mes heures supplémentaires"
    assert "IHTS" in expanded
    assert "indemnités horaires pour travaux supplémentaires" in expanded
    assert len(expanded) <= 6
    assert expand_legal_query("question sans terme juridique connu") == ["question sans terme juridique connu"]


def test_legal_query_expansion_is_accent_and_case_insensitive():
    expanded = expand_legal_query("CONGE MALADIE")
    assert "congé de maladie" in expanded
    assert "CMO" in expanded

@pytest.mark.asyncio
async def test_search_prioritizes_original_terms_over_fpt_expansions():
    from app.legal_corpus import search_legal_corpus

    class FakeConn:
        query = ""
        args = ()
        async def fetch(self, sql, *args):
            self.query = sql
            self.args = args
            return []

    conn = FakeConn()
    original = "Je ne suis pas payé pour mes heures supplémentaires"
    await search_legal_corpus(conn, original, date(2026, 1, 1))

    assert "2.0 * ts_rank_cd(c.search_vector,st.original_query)" in conn.query
    assert "ts_rank_cd(c.search_vector,st.expansion_query)" in conn.query
    assert "c.search_vector @@ st.original_query OR c.search_vector @@ st.expansion_query" in conn.query
    assert conn.args[0] == original
    assert "IHTS" in conn.args[1]
    assert len(conn.args) == 3
