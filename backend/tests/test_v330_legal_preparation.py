from datetime import date
from pathlib import Path
import importlib.util
import json

import pytest

from app.orchestrator import LegalOrchestrator
from app.schemas import AskRequest

@pytest.fixture(autouse=True)
def _mock_available_ai_catalog(monkeypatch):
    import app.orchestrator as module

    async def available():
        return {"status": "AVAILABLE"}

    monkeypatch.setattr(module, "check_provider_availability", available)


async def _fake_piste_token(self):
    return "test-access-token"




def _structured_claim(source, text, legal_context=None):
    evidence = source.get("excerpt") or source.get("text", "")[:1800]
    quote = " ".join(str(evidence).split())[:120]
    axes = (legal_context or {}).get("axes_recherche_documentaire") or []
    return json.dumps({
        "claims": [{
            "text": text,
            "source_id": source["source_id"],
            "axis": axes[0] if axes else "",
            "quote": quote,
        }],
        "uncovered_axes": axes[1:],
    }, ensure_ascii=False)


async def _always_supported(kwargs):
    return {"valid": True, "invalid": []}


def _enable_legifrance(monkeypatch, module):
    monkeypatch.setattr(type(module.legifrance), "configured", property(lambda self: True))
    monkeypatch.setattr(type(module.legifrance), "_get_token", _fake_piste_token)


@pytest.mark.asyncio
async def test_general_sick_leave_question_does_not_request_personal_facts_date(monkeypatch):
    import app.orchestrator as module

    called = False
    captured = {}

    async def bounded_snapshot_ai(**kwargs):
        nonlocal called
        called = True
        captured.update(kwargs)
        axes = (kwargs.get("legal_context") or {}).get("axes_recherche_documentaire") or []
        return json.dumps({"claims": [], "uncovered_axes": axes}, ensure_ascii=False)

    async def provider_available():
        return {"status": "AVAILABLE"}

    async def unavailable_research_plan(**kwargs):
        raise module.AIProviderUnavailable("CI deterministic fallback")

    monkeypatch.setattr(module, "plan_legal_research", unavailable_research_plan)
    monkeypatch.setattr(module, "analyze_question", bounded_snapshot_ai)
    monkeypatch.setattr(module, "check_provider_availability", provider_available)
    monkeypatch.setattr(type(module.legifrance), "configured", property(lambda self: False))
    response = await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", question="Quels sont les droits à congé maladie ?"),
        "00000000-0000-0000-0000-000000000001",
    )
    assert called is True
    assert any(
        source.get("source_type") == "CGFP_SNAPSHOT"
        and source.get("reference_role") == "CGFP_SNAPSHOT_FALLBACK_EVIDENCE"
        for source in captured["sources"]
    )
    assert response.clarification_question is None
    assert response.verification_status == "NON_VERIFIE"


def test_cgfp_import_script_validates_full_snapshot_and_article_count():
    script = Path(__file__).resolve().parents[2] / "scripts/import_cgfp_to_legal_corpus.py"
    spec = importlib.util.spec_from_file_location("import_cgfp_to_legal_corpus", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    root = Path(__file__).resolve().parents[2]
    metadata, articles = module.load_snapshot(
        root / "corpus_national/index/CGFP_articles_2026-10-31.json"
    )
    assert len(articles) == 4242
    assert metadata["verification_status"] == "SNAPSHOT_NOT_LIVE_VERIFIED"
    assert len({item["article"] for item in articles}) == 4242


def test_cgfp_import_script_rejects_tampered_pdf_hash(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/import_cgfp_to_legal_corpus.py"
    spec = importlib.util.spec_from_file_location("import_cgfp_to_legal_corpus_hash", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    index = Path(__file__).resolve().parents[2] / "corpus_national/index/CGFP_articles_2026-10-31.json"
    data = __import__("json").loads(index.read_text(encoding="utf-8"))
    data["source_sha256"] = "0" * 64
    # Keep the expected relative directory layout for the PDF lookup.
    (tmp_path / "index").mkdir()
    (tmp_path / "legislation").mkdir()
    pdf = index.parent.parent / "legislation" / data["source_file"]
    (tmp_path / "legislation" / data["source_file"]).write_bytes(pdf.read_bytes())
    test_index = tmp_path / "index" / "tampered.json"
    test_index.write_text(__import__("json").dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        module.load_snapshot(test_index)



def test_cgfp_import_requires_dedicated_ingestion_role():
    script = Path(__file__).resolve().parents[2] / "scripts/import_cgfp_to_legal_corpus.py"
    spec = importlib.util.spec_from_file_location("import_cgfp_to_legal_corpus_role", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    module.validate_ingest_dsn(
        "postgresql://cfdt_juris_ingest:secret@db.example/cfdt_juris"
    )
    with pytest.raises(ValueError, match="rôle dédié"):
        module.validate_ingest_dsn(
            "postgresql://cfdt_juris_app:secret@db.example/cfdt_juris"
        )
    with pytest.raises(ValueError, match="URL PostgreSQL"):
        module.validate_ingest_dsn("https://example.invalid/database")


def test_cgfp_import_uses_separate_ingestion_environment_variable():
    script = Path(__file__).resolve().parents[2] / "scripts/import_cgfp_to_legal_corpus.py"
    source = script.read_text(encoding="utf-8")
    assert 'default=os.getenv("LEGAL_CORPUS_INGEST_DATABASE_URL")' in source
    assert 'default=os.getenv("DATABASE_URL")' not in source



def test_fresh_schema_accepts_cgfp_snapshot_source_type():
    schema = Path(__file__).resolve().parents[2] / "database/schema.sql"
    source = schema.read_text(encoding="utf-8")
    assert "'CGFP_SNAPSHOT'" in source



@pytest.mark.asyncio
async def test_orchestrator_uses_date_scoped_loda_texts_as_regulatory_sources(monkeypatch):
    import app.orchestrator as module

    _enable_legifrance(monkeypatch, module)

    async def no_code_articles(*args, **kwargs):
        return []

    searched_dates = []
    monkeypatch.setattr(module, "_france_today", lambda: date(2026, 11, 21))

    async def regulatory_texts(query, effective_date, limit=5):
        searched_dates.append(effective_date)
        assert limit == 3
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000000000001",
            "title": "Décret relatif à la fonction publique territoriale",
            "document_kind": "DECREE",
            "official_number": "2024-100",
            "official_url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000001",
            "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
            "full_text": "Texte officiel du décret relatif aux agents territoriaux. " * 100,
        }]

    async def no_case_law(*args, **kwargs):
        return []

    captured = {}

    async def fake_ai(**kwargs):
        captured["sources"] = kwargs["sources"]
        source = next(s for s in kwargs["sources"] if s["source_type"] == "LEGIFRANCE_LODA")
        return _structured_claim(source, "Le décret n° 2024-100 doit être vérifié au regard de la situation exposée.", kwargs.get("legal_context"))

    monkeypatch.setattr(module.legifrance, "search_code_articles", no_code_articles)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", regulatory_texts)
    monkeypatch.setattr(module.case_law_connector, "search", no_case_law)
    monkeypatch.setattr(module, "analyze_question", fake_ai)
    monkeypatch.setattr(module, "verify_claim_entailment", lambda **kwargs: _always_supported(kwargs))

    response = await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", facts_date="2024-06-01",
                   question="Quelles règles encadrent les agents territoriaux ?"),
        "00000000-0000-0000-0000-000000000001",
    )
    assert date(2024, 6, 1) in searched_dates
    assert date(2026, 11, 21) in searched_dates
    assert response.verification_status == "PARTIELLEMENT_VERIFIE"
    assert response.answer.startswith("Le décret n° 2024-100")
    assert "Voici ce que les textes permettent de comprendre" not in response.answer
    loda_response = next(s for s in response.sources if s["source_type"] == "LEGIFRANCE_LODA")
    assert loda_response["version_role"] == "FACTS_DATE_VERSION"
    assert loda_response["requested_effective_date"] == "2024-06-01"
    assert len(loda_response["text"]) <= 1800
    assert "full_text" not in loda_response
    assert any(s["source_type"] == "LEGIFRANCE_LODA" for s in captured["sources"])



@pytest.mark.asyncio
async def test_live_legal_searches_prioritize_current_question_and_respect_500_char_limit(monkeypatch):
    import app.orchestrator as module

    _enable_legifrance(monkeypatch, module)
    seen = {"code": [], "regulatory": [], "case_law": []}

    async def capture_code(query, *args, **kwargs):
        seen["code"].append(query)
        return []

    async def capture_regulatory(query, *args, **kwargs):
        seen["regulatory"].append(query)
        return []

    async def capture_case_law(query, *args, **kwargs):
        seen["case_law"].append(query)
        return []

    monkeypatch.setattr(module.legifrance, "search_code_articles", capture_code)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", capture_regulatory)
    monkeypatch.setattr(module.case_law_connector, "search", capture_case_law)

    current_question = "Question actuelle sur le temps de travail. " * 20
    primary_prefix = current_question.strip()[:250]
    history = [{"role": "user", "content": "Ancienne question sans rapport. " * 50}]
    await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", question=current_question),
        "00000000-0000-0000-0000-000000000001",
        conversation_history=history,
    )

    # Preserve all recognized code-research axes, then reserve capacity for
    # up to three exact article lookups (maximum eight bounded code searches).
    # Regulatory and case-law budgets remain unchanged.
    assert 3 <= len(seen["code"]) <= 8
    assert len(seen["regulatory"]) == 3
    assert len(seen["case_law"]) == 3
    all_queries = [query for pillar in seen.values() for query in pillar]
    assert all(len(query) <= 500 for query in all_queries)
    assert all_queries[0].startswith(primary_prefix)
    assert all("Ancienne question sans rapport" not in query for query in all_queries)
    assert any("décret 2001-623" in query for query in all_queries)



@pytest.mark.asyncio
async def test_ai_does_not_use_current_cgfp_snapshot_for_historical_facts(monkeypatch):
    import app.orchestrator as module

    captured = {}

    async def bounded_snapshot_ai(**kwargs):
        captured["sources"] = kwargs["sources"]
        axes = (kwargs.get("legal_context") or {}).get("axes_recherche_documentaire") or []
        return json.dumps({"claims": [], "uncovered_axes": axes}, ensure_ascii=False)

    async def provider_available():
        return {"status": "AVAILABLE"}

    monkeypatch.setattr(module, "analyze_question", bounded_snapshot_ai)
    monkeypatch.setattr(module, "check_provider_availability", provider_available)
    monkeypatch.setattr(type(module.legifrance), "configured", property(lambda self: False))

    response = await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", facts_date="2024-06-01",
                   question="Quels sont les droits des agents territoriaux ?"),
        "00000000-0000-0000-0000-000000000001",
    )
    assert captured == {}
    assert not any(source.get("source_type") == "CGFP_SNAPSHOT" for source in response.sources)
    assert response.verification_status == "NON_VERIFIE"
    assert "Aucune conclusion juridique" in response.answer



def test_cgfp_import_rejects_path_traversal_in_source_filename(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/import_cgfp_to_legal_corpus.py"
    spec = importlib.util.spec_from_file_location("import_cgfp_to_legal_corpus_path", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    source_index = Path(__file__).resolve().parents[2] / "corpus_national/index/CGFP_articles_2026-10-31.json"
    data = __import__("json").loads(source_index.read_text(encoding="utf-8"))
    data["source_file"] = "../../outside.pdf"
    (tmp_path / "index").mkdir()
    (tmp_path / "legislation").mkdir()
    test_index = tmp_path / "index" / "bad-path.json"
    test_index.write_text(__import__("json").dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="Nom de PDF source invalide"):
        module.load_snapshot(test_index)


def test_cgfp_import_rejects_article_page_outside_pdf(tmp_path):
    script = Path(__file__).resolve().parents[2] / "scripts/import_cgfp_to_legal_corpus.py"
    spec = importlib.util.spec_from_file_location("import_cgfp_to_legal_corpus_pages", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    source_index = Path(__file__).resolve().parents[2] / "corpus_national/index/CGFP_articles_2026-10-31.json"
    data = __import__("json").loads(source_index.read_text(encoding="utf-8"))
    data["articles"][0]["page_end"] = 1025
    (tmp_path / "index").mkdir()
    (tmp_path / "legislation").mkdir()
    pdf = source_index.parent.parent / "legislation" / data["source_file"]
    (tmp_path / "legislation" / data["source_file"]).write_bytes(pdf.read_bytes())
    test_index = tmp_path / "index" / "bad-page.json"
    test_index.write_text(__import__("json").dumps(data), encoding="utf-8")
    with pytest.raises(ValueError, match="hors PDF"):
        module.load_snapshot(test_index)



def test_cgfp_snapshot_import_never_preserves_a_previous_verified_source_status():
    script = Path(__file__).resolve().parents[2] / "scripts/import_cgfp_to_legal_corpus.py"
    source = script.read_text(encoding="utf-8")
    assert "source_status='IMPORTED_UNVERIFIED'" in source
    assert "OFFICIAL_TEXT_RETRIEVED" not in source
    assert "MANUALLY_VERIFIED" not in source



@pytest.mark.asyncio
async def test_cgfp_import_batches_chunk_inserts_inside_one_transaction(monkeypatch):
    import sys
    from types import SimpleNamespace

    script = Path(__file__).resolve().parents[2] / "scripts/import_cgfp_to_legal_corpus.py"
    spec = importlib.util.spec_from_file_location("import_cgfp_to_legal_corpus_batch", script)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)

    class Transaction:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False

    class FakeConnection:
        def __init__(self):
            self.fetch_calls = []
            self.batch_calls = []
            self.closed = False
        def transaction(self):
            return Transaction()
        async def fetchrow(self, query, *args):
            self.fetch_calls.append((query, args))
            if "FROM legal_source_registry" in query:
                return {"metadata_ingestion_allowed": True, "full_text_ingestion_allowed": True}
            if "bad_temporal_status" in query:
                return {
                    "documents": 2, "versions": 2, "chunks": 2,
                    "bad_document_status": 0, "bad_temporal_status": 0,
                }
            return {"id": f"version-{len(self.fetch_calls)}"}
        async def executemany(self, query, records):
            self.batch_calls.append((query, list(records)))
        async def close(self):
            self.closed = True

    fake_conn = FakeConnection()

    async def fake_connect(dsn, **kwargs):
        assert dsn.startswith("postgresql://cfdt_juris_ingest:")
        assert kwargs.get("command_timeout") == 120
        return fake_conn

    monkeypatch.setitem(sys.modules, "asyncpg", SimpleNamespace(connect=fake_connect))
    metadata = {
        "source_id": "FR-CGFP-TEST",
        "source_sha256": "a" * 64,
        "source_file": "test.pdf",
    }
    articles = [
        {"article": "L1", "text": "Texte de l'article un.", "page_start": 1, "page_end": 1},
        {"article": "L2", "text": "Texte de l'article deux.", "page_start": 2, "page_end": 2},
    ]
    result = await module.import_snapshot(
        "postgresql://cfdt_juris_ingest:secret@db/cfdt_juris", metadata, articles
    )

    assert result == {"articles": 2, "versions": 2, "chunks": 2}
    assert len(fake_conn.fetch_calls) == 4
    assert "FROM legal_source_registry" in fake_conn.fetch_calls[0][0]
    assert all("WITH upserted_document" in call[0] for call in fake_conn.fetch_calls[1:3])
    assert "bad_temporal_status" in fake_conn.fetch_calls[3][0]
    assert len(fake_conn.batch_calls) == 1
    assert len(fake_conn.batch_calls[0][1]) == 2
    assert fake_conn.closed is True



@pytest.mark.asyncio
async def test_ai_receives_cgfp_as_baseline_context_not_temporal_proof(monkeypatch):
    import app.orchestrator as module

    _enable_legifrance(monkeypatch, module)

    async def no_code_articles(*args, **kwargs):
        return []

    async def regulatory_texts(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000000000001",
            "title": "Décret relatif à la fonction publique territoriale",
            "document_kind": "DECREE",
            "jurisdiction": "France",
            "official_number": "2024-100",
            "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
            "full_text": "Texte officiel suffisamment long pour être exploitable. " * 10,
        }]

    async def no_case_law(*args, **kwargs):
        return []

    async def unsupported_ai(**kwargs):
        snapshots = [s for s in kwargs["sources"] if s.get("source_type") == "CGFP_SNAPSHOT"]
        assert not snapshots  # Live Légifrance CGFP lookup succeeded; PDF is not consulted.
        assert any(s.get("source_type") == "LEGIFRANCE_LODA" for s in kwargs["sources"])
        source = next(s for s in kwargs["sources"] if s["source_type"] == "LEGIFRANCE_LODA")
        return _structured_claim(source, "L'article L4 prévoit cette règle.")

    monkeypatch.setattr(module.legifrance, "search_code_articles", no_code_articles)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", regulatory_texts)
    monkeypatch.setattr(module.case_law_connector, "search", no_case_law)
    monkeypatch.setattr(module, "analyze_question", unsupported_ai)

    response = await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", facts_date="2024-06-01",
                   question="Quels droits pour les agents territoriaux ?"),
        "00000000-0000-0000-0000-000000000001",
    )
    assert any("réponse IA a été bloquée" in item for item in response.missing_information)
    assert "L'article L4 prévoit cette règle." not in response.answer
    snapshot_sources = [s for s in response.sources if s.get("source_type") == "CGFP_SNAPSHOT"]
    assert not snapshot_sources



@pytest.mark.asyncio
async def test_orchestrator_uses_only_verified_local_documents_for_local_employer(monkeypatch):
    import app.orchestrator as module

    _enable_legifrance(monkeypatch, module)
    async def no_permanent(*args, **kwargs):
        return []

    monkeypatch.setattr(module, "search_legal_corpus", no_permanent)
    local_source = {
        "source_type": "LOCAL_DOCUMENT",
        "source_id": "LOCAL-DOC:00000000-0000-0000-0000-000000000123",
        "title": "Délibération sur le temps de travail",
        "document_kind": "LOCAL_DOCUMENT",
        "local_document_type": "DELIBERATION",
        "official_number": "DEL-2024-12",
        "collectivity": "Ville de Saint-Étienne",
        "validation_status": "VERIFIED_APPLICABLE",
        "temporal_status": "VERIFIED_APPLICABLE",
        "effective_from": "2020-01-01",
        "content_kind": "FULL_TEXT",
        "excerpt": "Extrait validé de la délibération.",
        "text": "Extrait validé de la délibération.",
        "citation_integrity": {"valid": True},
        "version_endpoint": "START",
    }

    async def local_search(*args, **kwargs):
        return [local_source]

    captured = {}

    async def fake_ai(**kwargs):
        captured["sources"] = kwargs["sources"]
        source = next(s for s in kwargs["sources"] if s["source_type"] == "LOCAL_DOCUMENT")
        return _structured_claim(source, "L'article L. 123-4 doit être examiné avec la délibération locale.")

    async def code_articles(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_API", "source_id": "LEGIARTI000000000123",
            "article": "L123-4", "title": "Code général de la fonction publique — article L. 123-4",
            "text": "Article L. 123-4 : dispositions applicables aux agents publics territoriaux. " * 8,
            "excerpt": "Article L. 123-4 : dispositions applicables aux agents publics territoriaux.",
        }]

    async def no_regulatory(*args, **kwargs):
        return []

    async def no_case_law(*args, **kwargs):
        return []

    monkeypatch.setattr(module.legifrance, "search_code_articles", code_articles)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", no_regulatory)
    monkeypatch.setattr(module.case_law_connector, "search", no_case_law)
    monkeypatch.setattr(module, "is_ihts_relevant_source", lambda *args, **kwargs: True)
    monkeypatch.setattr(module, "search_local_documents", local_search)
    monkeypatch.setattr(module, "analyze_question", fake_ai)
    monkeypatch.setattr(module, "verify_claim_entailment", lambda **kwargs: _always_supported(kwargs))

    response = await LegalOrchestrator().ask(
        AskRequest(employer="VILLE_SAINT_ETIENNE", facts_date="2024-06-01",
                   question="Quelles règles locales encadrent le temps de travail ?"),
        "00000000-0000-0000-0000-000000000001",
        conn=object(),
    )
    assert response.verification_status == "PARTIELLEMENT_VERIFIE"
    assert any(s["source_type"] == "LOCAL_DOCUMENT" for s in response.sources)
    assert any(s["source_type"] == "LOCAL_DOCUMENT" for s in captured["sources"])


@pytest.mark.asyncio
async def test_orchestrator_does_not_use_unverified_local_documents_for_ai(monkeypatch):
    import app.orchestrator as module

    monkeypatch.setattr(type(module.legifrance), "configured", property(lambda self: False))
    async def no_permanent(*args, **kwargs):
        return []

    monkeypatch.setattr(module, "search_legal_corpus", no_permanent)
    called = False

    async def local_search(*args, **kwargs):
        return [{
            "source_type": "LOCAL_DOCUMENT",
            "source_id": "LOCAL-DOC:00000000-0000-0000-0000-000000000123",
            "title": "Document local non vérifié",
            "document_kind": "LOCAL_DOCUMENT",
            "local_document_type": "DELIBERATION",
            "validation_status": "COLLECTED_UNVERIFIED",
            "temporal_status": "LOCAL_VALIDATION_INCOMPLETE",
            "content_kind": "FULL_TEXT",
            "excerpt": "Extrait non validé.",
            "text": "Extrait non validé.",
            "citation_integrity": {"valid": True},
        }]

    async def forbidden_ai(**kwargs):
        nonlocal called
        called = True
        raise AssertionError("Un document local non validé ne doit pas être envoyé à l'IA.")

    monkeypatch.setattr(module, "search_local_documents", local_search)
    monkeypatch.setattr(module, "analyze_question", forbidden_ai)

    response = await LegalOrchestrator().ask(
        AskRequest(employer="VILLE_SAINT_ETIENNE", facts_date="2024-06-01",
                   question="Quelles règles locales encadrent le temps de travail ?"),
        "00000000-0000-0000-0000-000000000001",
        conn=object(),
    )
    assert called is False
    assert response.verification_status == "NON_VERIFIE"
    assert any("validation humaine" in item for item in response.missing_information)



@pytest.mark.asyncio
async def test_follow_up_search_context_keeps_current_question_first(monkeypatch):
    import app.orchestrator as module

    monkeypatch.setattr(type(module.legifrance), "configured", property(lambda self: False))
    captured = {"queries": []}

    def capture_cgfp(query, limit=8):
        captured["queries"].append(query)
        return None

    monkeypatch.setattr(module, "search_cgfp", capture_cgfp)
    response = await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", question="Et pour les contractuels ?"),
        "00000000-0000-0000-0000-000000000001",
        conversation_history=[
            {"role": "user", "content": "Ancienne question sur les congés maladie."},
            {"role": "user", "content": "Question précédente sur les fonctionnaires titulaires."},
        ],
    )
    assert captured["queries"][0].startswith("Et pour les contractuels ?")
    assert any("Question précédente sur les fonctionnaires titulaires." in query for query in captured["queries"])
    assert all("Ancienne question sur les congés maladie." not in query for query in captured["queries"])
    assert response.verification_status == "NON_VERIFIE"



@pytest.mark.asyncio
async def test_unverified_permanent_corpus_source_is_excluded_from_ai_even_with_a_valid_hash(monkeypatch):
    import app.orchestrator as module

    _enable_legifrance(monkeypatch, module)

    async def no_code(*args, **kwargs):
        return []

    async def regulatory(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000000000001",
            "title": "Décret relatif aux collectivités territoriales",
            "document_kind": "DECREE",
            "jurisdiction": "France",
            "official_number": "2024-100",
            "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
            "full_text": "Texte officiel complet du décret. " * 10,
            "excerpt": "Texte officiel complet du décret.",
        }]

    async def no_case_law(*args, **kwargs):
        return []

    async def permanent(*args, **kwargs):
        return [{
            "source_type": "OTHER_OFFICIAL",
            "source_id": "UNVERIFIED-001",
            "title": "Texte importé sans date d'effet",
            "document_kind": "OTHER",
            "content_kind": "FULL_TEXT",
            "text": "Texte importé.",
            "excerpt": "Texte importé.",
            "source_status": "OFFICIAL_XML_IMPORTED",
            "temporal_status": "TEMPORAL_SCOPE_INCOMPLETE",
            "citation_integrity": {"valid": True},
        }]

    captured = {}

    async def fake_ai(**kwargs):
        captured["sources"] = kwargs["sources"]
        source = next(s for s in kwargs["sources"] if s["source_type"] == "LEGIFRANCE_LODA")
        return _structured_claim(source, "Le décret n° 2024-100 doit être examiné.")

    monkeypatch.setattr(module.legifrance, "search_code_articles", no_code)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", regulatory)
    monkeypatch.setattr(module.case_law_connector, "search", no_case_law)
    monkeypatch.setattr(module, "search_legal_corpus", permanent)
    monkeypatch.setattr(module, "analyze_question", fake_ai)
    monkeypatch.setattr(module, "verify_claim_entailment", lambda **kwargs: _always_supported(kwargs))

    await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", facts_date="2024-06-01",
                   question="Quels textes encadrent la fonction publique territoriale ?"),
        "00000000-0000-0000-0000-000000000001",
        conn=object(),
    )
    assert any(s["source_type"] == "LEGIFRANCE_LODA" for s in captured["sources"])
    assert all(s["source_type"] != "OTHER_OFFICIAL" for s in captured["sources"])



@pytest.mark.asyncio
async def test_current_date_repere_sources_are_not_labelled_applicable_without_facts_date(monkeypatch):
    import app.orchestrator as module

    _enable_legifrance(monkeypatch, module)

    async def code_sources(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_API", "source_id": "LEGIARTI000000000001",
            "article": "L123-4", "title": "Article L123-4", "text": "Texte officiel.",
            "excerpt": "Texte officiel.",
        }]

    async def loda_sources(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_LODA", "source_id": "LEGITEXT000000000001",
            "title": "Décret", "document_kind": "DECREE",
            "full_text": "Texte officiel du décret. " * 5,
            "excerpt": "Texte officiel du décret.",
        }]

    async def no_case_law(*args, **kwargs):
        return []

    async def forbidden_ai(**kwargs):
        raise AssertionError("Pas d'analyse contextualisée sans date des faits.")

    monkeypatch.setattr(module.legifrance, "search_code_articles", code_sources)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", loda_sources)
    monkeypatch.setattr(module.case_law_connector, "search", no_case_law)
    monkeypatch.setattr(module, "analyze_question", forbidden_ai)

    response = await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", question="Quels textes encadrent les agents territoriaux ?"),
        "00000000-0000-0000-0000-000000000001",
    )
    official_sources = [
        source for source in response.sources
        if source.get("source_type") in {"LEGIFRANCE_API", "LEGIFRANCE_LODA"}
    ]
    assert official_sources
    assert all(source.get("temporal_status") == "VERSION_RETRIEVED_AT_REQUESTED_DATE"
               for source in official_sources)
    assert all(source.get("version_role") == "CURRENT_LAW_VERSION"
               and source.get("general_info_eligible") is True
               for source in official_sources)


@pytest.mark.asyncio
async def test_ihts_query_retrieves_decree_91_875_and_filters_irrelevant_cgfp_hits(monkeypatch):
    import app.orchestrator as module

    _enable_legifrance(monkeypatch, module)

    async def code_articles(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_API",
            "source_id": "LEGIARTI000000000431",
            "article": "R431-3",
            "title": "Code général de la fonction publique — article R431-3",
            "text": (
                "Les périodes d'astreintes mentionnées à l'article 5 du décret "
                "n° 2001-623 du 12 juillet 2001 ne constituent pas du télétravail."
            ) * 2,
        }]

    calls = []

    async def regulatory_texts(query, effective_date, limit=3):
        calls.append(query)
        if "91-875" in query:
            text = (
                "Le présent décret fixe les conditions du régime indemnitaire "
                "applicable aux fonctionnaires territoriaux et aux collectivités territoriales."
            )
            return [{
                "source_type": "LEGIFRANCE_LODA",
                "source_id": "LEGITEXT000000000875",
                "title": "Décret n° 91-875 relatif au régime indemnitaire des collectivités territoriales",
                "document_kind": "DECREE",
                "official_number": "91-875",
                "official_url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000875",
                "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
                "full_text": text,
                "excerpt": text,
            }]
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000000000260",
            "title": "Décret n° 2002-60 relatif aux indemnités horaires pour travaux supplémentaires",
            "document_kind": "DECREE",
            "official_number": "2002-60",
            "official_url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000260",
            "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
            "full_text": (
                "Le décret concerne les indemnités horaires pour travaux supplémentaires. "
                "Il doit être rapproché du régime indemnitaire territorial."
            ) * 4,
        }]

    async def no_case_law(*args, **kwargs):
        return []

    captured = {}

    async def fake_ai(**kwargs):
        captured["sources"] = kwargs["sources"]
        source = next(s for s in kwargs["sources"] if s.get("official_number") == "91-875")
        return _structured_claim(
            source,
            "Le décret n° 91-875 concerne le régime indemnitaire des fonctionnaires territoriaux.",
            kwargs.get("legal_context"),
        )

    monkeypatch.setattr(module.legifrance, "search_code_articles", code_articles)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", regulatory_texts)
    monkeypatch.setattr(module.case_law_connector, "search", no_case_law)
    monkeypatch.setattr(module, "analyze_question", fake_ai)
    monkeypatch.setattr(module, "verify_claim_entailment", lambda **kwargs: _always_supported(kwargs))

    response = await LegalOrchestrator().ask(
        AskRequest(employer="NATIONAL", question="On me paie pas mes heures supplémentaires."),
        "00000000-0000-0000-0000-000000000001",
    )

    assert any("91-875" in query for query in calls)
    assert all(source.get("article") != "R431-3" for source in response.sources)
    assert any(source.get("official_number") == "91-875" for source in captured["sources"])
    assert all(source.get("article") != "R431-3" for source in captured["sources"])
    assert response.verification_status == "PARTIELLEMENT_VERIFIE"



@pytest.mark.asyncio
async def test_unanswerable_question_does_not_dump_legal_excerpts_into_answer(monkeypatch):
    import app.orchestrator as module

    _enable_legifrance(monkeypatch, module)

    async def no_code_articles(*args, **kwargs):
        return []

    exact_excerpt = (
        "Les agents territoriaux bénéficient des dispositions réglementaires "
        "relatives à l'organisation du service et aux conditions de travail. "
    ) * 8

    async def regulatory_texts(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT000000000099",
            "title": "Décret relatif à l'organisation des services territoriaux",
            "document_kind": "DECREE",
            "official_number": "2024-999",
            "official_url": "https://www.legifrance.gouv.fr/loda/id/LEGITEXT000000000099",
            "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
            "full_text": exact_excerpt,
        }]

    async def no_case_law(*args, **kwargs):
        return []

    async def no_supported_claims(**kwargs):
        return '{"claims": []}'

    monkeypatch.setattr(module.legifrance, "search_code_articles", no_code_articles)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", regulatory_texts)
    monkeypatch.setattr(module.case_law_connector, "search", no_case_law)
    monkeypatch.setattr(module, "analyze_question", no_supported_claims)

    response = await LegalOrchestrator().ask(
        AskRequest(
            employer="NATIONAL",
            facts_date="2024-06-01",
            question="Mon employeur a refusé ma demande de mobilité : quels recours ?",
        ),
        "00000000-0000-0000-0000-000000000001",
    )
    assert exact_excerpt[:100] not in response.answer
    assert "plutôt que de recopier des articles" in response.answer
    assert "Sources retrouvées" in response.answer

@pytest.mark.asyncio
async def test_permanent_corpus_version_status_survives_orchestration_for_general_questions(monkeypatch):
    import app.orchestrator as module

    _enable_legifrance(monkeypatch, module)

    async def no_code(*args, **kwargs):
        return []

    async def no_regulatory(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_LODA",
            "source_id": "LEGITEXT_LIVE_CONTROL_001",
            "title": "Décret relatif à la fonction publique territoriale",
            "document_kind": "DECREE",
            "official_number": "2024-100",
            "source_status": "OFFICIAL_TEXT_ID_VERIFIED",
            "full_text": "Les agents de la fonction publique territoriale bénéficient des garanties prévues par le présent décret. " * 5,
            "excerpt": "Les agents de la fonction publique territoriale bénéficient des garanties prévues par le présent décret. " * 5,
        }]

    async def no_case_law(*args, **kwargs):
        return []

    async def permanent(*args, **kwargs):
        return [{
            "source_type": "LEGIFRANCE_LEGI",
            "source_id": "LEGITEXT_REPEALED_001",
            "title": "Code relatif à la fonction publique territoriale",
            "document_kind": "CODE",
            "content_kind": "FULL_TEXT",
            "excerpt": "Les agents de la fonction publique territoriale bénéficient des garanties prévues par le présent code. " * 3,
            "full_text": "Les agents de la fonction publique territoriale bénéficient des garanties prévues par le présent code. " * 3,
            "source_status": "OFFICIAL_TEXT_RETRIEVED",
            "version_status": "REPEALED",
            "temporal_status": "TEMPORAL_SCOPE_INCOMPLETE",
            "citation_integrity": {"valid": True},
            "raw_metadata": {},
        }]

    captured = {}

    async def fake_ai(**kwargs):
        captured["sources"] = kwargs["sources"]
        return '{"claims": []}'

    monkeypatch.setattr(module.legifrance, "search_code_articles", no_code)
    monkeypatch.setattr(module.legifrance, "search_regulatory_texts", no_regulatory)
    monkeypatch.setattr(module.case_law_connector, "search", no_case_law)
    monkeypatch.setattr(module, "search_legal_corpus", permanent)
    monkeypatch.setattr(module, "analyze_question", fake_ai)

    response = await LegalOrchestrator().ask(
        AskRequest(
            employer="NATIONAL",
            question="Quelles règles encadrent la fonction publique territoriale ?",
        ),
        "00000000-0000-0000-0000-000000000001",
        conn=object(),
    )

    imported_source = next(
        source for source in response.sources
        if source.get("source_id") == "LEGITEXT_REPEALED_001"
    )
    assert imported_source["version_status"] == "REPEALED"
    assert imported_source["general_info_eligible"] is False
    assert all(
        source.get("source_id") != "LEGITEXT_REPEALED_001"
        for source in captured["sources"]
    )
