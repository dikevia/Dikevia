from datetime import date

import pytest

from app.legal_corpus import search_legal_corpus


class FakeConn:
    def __init__(self):
        self.query = None
        self.args = None

    async def fetch(self, query, *args):
        self.query = query
        self.args = args
        return []


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
