from datetime import date

import pytest

from app.legal_corpus import search_legal_corpus


class FakeConn:
    def __init__(self, rows=None):
        self.query = None
        self.args = None
        self.rows = rows or []

    async def fetch(self, query, *args):
        self.query = query
        self.args = args
        return self.rows


@pytest.mark.asyncio
async def test_corpus_search_applies_bounded_authority_weight_only_to_verified_official_text():
    conn = FakeConn()

    results = await search_legal_corpus(
        conn,
        "congé maladie fonction publique",
        date(2026, 11, 24),
        limit=12,
    )

    assert results == []
    assert conn.query is not None
    assert "authority_weight" in conn.query
    assert "v.source_version_id" in conn.query
    assert "v.version_key" in conn.query
    assert "source_version_id,version_key" in conn.query
    assert "max(rank * authority_weight) AS rank" in conn.query
    assert "\\n        SELECT version_id" not in conn.query
    assert "validation.\n        SELECT version_id,string_agg" in conn.query
    assert "THEN 1.15" in conn.query
    assert "WHEN d.source_type IN ('LEGIFRANCE_CETAT','OTHER_OFFICIAL') AND d.document_kind='ADMIN_CASELAW'" in conn.query
    assert "THEN 1.10" in conn.query
    assert "THEN 1.05" in conn.query
    assert "ELSE 1.0" in conn.query
    assert "OFFICIAL_TEXT_RETRIEVED" in conn.query
    assert "MANUALLY_VERIFIED" in conn.query
    assert "SERVICE_PUBLIC_PART" not in conn.query.split("CASE", 1)[1].split("END AS authority_weight", 1)[0]
    assert "INSTITUTIONAL_GUIDANCE" not in conn.query.split("CASE", 1)[1].split("END AS authority_weight", 1)[0]


@pytest.mark.asyncio
async def test_corpus_search_preserves_verified_text_hash_and_version_provenance():
    from app.legal_corpus import sha256_text

    full_text = (
        "L'agent public bénéficie des dispositions applicables prévues par le présent article. "
        "Le texte précise les conditions et les garanties statutaires."
    )
    stored_hash = sha256_text(full_text)
    conn = FakeConn([{
        "document_id": "00000000-0000-0000-0000-000000000101",
        "version_id": "00000000-0000-0000-0000-000000000202",
        "source_type": "LEGIFRANCE_LEGI",
        "source_id": "LEGITEXT000000000001",
        "title": "Code général de la fonction publique",
        "document_kind": "CODE",
        "official_number": "CGFP",
        "jurisdiction": "FR",
        "official_url": "https://www.legifrance.gouv.fr/",
        "signature_date": None,
        "publication_date": date(2024, 1, 1),
        "document_status": "UNKNOWN",
        "source_status": "OFFICIAL_TEXT_RETRIEVED",
        "raw_metadata": {},
        "source_version_id": "LEGIARTI000000000001",
        "version_key": "2024-01-01",
        "valid_from": date(2024, 1, 1),
        "valid_to": date(2024, 12, 31),
        "version_status": "IN_FORCE",
        "raw_payload": {"requested_date": "2024-06-01"},
        "full_text": full_text,
        "text_sha256": stored_hash,
        "anchor": "Article L123-1",
        "content_kind": "FULL_TEXT",
        "ordinal": 0,
        "content": full_text,
        "rank": 0.5,
    }])

    results = await search_legal_corpus(
        conn, "conditions statutaires", date(2024, 6, 1), limit=12
    )

    assert len(results) == 1
    source = results[0]
    assert source["text_sha256"] == stored_hash
    assert source["source_version_id"] == "LEGIARTI000000000001"
    assert source["version_key"] == "2024-01-01"
    assert source["version_id"] == "00000000-0000-0000-0000-000000000202"
    assert source["full_text"] == full_text
    assert source["citation_integrity"]["valid"] is True
    assert source["citation_integrity"]["text_hash_verified"] is True


@pytest.mark.asyncio
async def test_upsert_fills_official_source_version_id_when_same_version_is_reingested():
    from app.legal_corpus import upsert_legal_document

    class WriteConn:
        def __init__(self):
            self.fetchrow_calls = []
            self.execute_calls = []

        async def fetchrow(self, query, *args):
            self.fetchrow_calls.append((query, args))
            return {"id": "document-id" if len(self.fetchrow_calls) == 1 else "version-id"}

        async def execute(self, query, *args):
            self.execute_calls.append((query, args))

    conn = WriteConn()
    result = await upsert_legal_document(conn, {
        "source_type": "LEGIFRANCE_LEGI",
        "source_id": "LEGITEXT000000000001",
        "source_version_id": "LEGIARTI000000000001",
        "title": "Code général de la fonction publique",
        "document_kind": "CODE",
        "version_key": "2024-01-01",
        "full_text": "Article L123-1. " + ("Texte juridique vérifié. " * 10),
        "source_status": "OFFICIAL_TEXT_RETRIEVED",
    })

    version_query, version_args = conn.fetchrow_calls[1]
    assert "source_version_id=COALESCE(EXCLUDED.source_version_id,legal_document_versions.source_version_id)" in version_query
    assert version_args[2] == "LEGIARTI000000000001"
    assert result["version_id"] == "version-id"
    assert conn.execute_calls


def test_corpus_interleaving_preserves_distinct_versions_of_the_same_document():
    from app.legal_corpus import interleave_legal_corpus_results

    first_version = {
        "source_id": "LEGITEXT000000000001",
        "version_id": "version-2024",
        "excerpt": "Ancienne rédaction",
    }
    second_version = {
        "source_id": "LEGITEXT000000000001",
        "version_id": "version-2025",
        "excerpt": "Nouvelle rédaction",
    }
    repeated_first_version = {**first_version, "retrieval_mode": "VECTOR"}

    selected = interleave_legal_corpus_results(
        [[first_version, second_version], [repeated_first_version]],
        limit=12,
    )

    assert selected == [first_version, second_version]


def test_corpus_interleaving_falls_back_to_stable_source_id_without_version_id():
    from app.legal_corpus import interleave_legal_corpus_results

    first = {"source_id": "LEGITEXT000000000001", "excerpt": "Passage lexical"}
    duplicate = {"source_id": "LEGITEXT000000000001", "excerpt": "Passage vectoriel"}

    selected = interleave_legal_corpus_results([[first], [duplicate]], limit=12)

    assert selected == [first]


def test_corpus_version_citation_ids_distinguish_versions_of_one_official_document():
    from app.legal_corpus import corpus_version_citation_id

    official_id = "LEGITEXT000000000001"
    first = corpus_version_citation_id(official_id, "11111111-1111-4111-8111-111111111111")
    second = corpus_version_citation_id(official_id, "22222222-2222-4222-8222-222222222222")

    assert first != second
    assert first.startswith("CORPUS_VERSION_")
    assert second.startswith("CORPUS_VERSION_")
    assert corpus_version_citation_id(official_id, None) == official_id
    assert corpus_version_citation_id(None, "11111111-1111-4111-8111-111111111111") is None

@pytest.mark.asyncio
async def test_corpus_search_uses_normalized_384d_query_vector_in_hybrid_ranking():
    conn = FakeConn()

    await search_legal_corpus(
        conn,
        "temps de travail fonction publique",
        date(2026, 11, 24),
        limit=12,
        query_embedding=[3.0] + [4.0] + [0.0] * 382,
    )

    assert "vector_ranked AS" in conn.query
    assert "c.embedding_384 <=> $4::vector" in conn.query
    assert conn.args[3].startswith("[0.60000000,0.80000000,")
    assert conn.args[3].endswith("0.00000000]")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "embedding",
    [
        [1.0] * 383,
        [0.0] * 384,
        [float("nan")] + [0.0] * 383,
        [float("inf")] + [0.0] * 383,
    ],
)
async def test_corpus_search_rejects_invalid_query_embeddings_before_database_access(embedding):
    conn = FakeConn()

    with pytest.raises(ValueError):
        await search_legal_corpus(
            conn,
            "temps de travail fonction publique",
            date(2026, 11, 24),
            query_embedding=embedding,
        )

    assert conn.query is None
