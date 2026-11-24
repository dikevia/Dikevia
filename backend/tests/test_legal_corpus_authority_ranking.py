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
    assert "max(rank * authority_weight) AS rank" in conn.query
    assert "THEN 1.15" in conn.query
    assert "THEN 1.10" in conn.query
    assert "THEN 1.05" in conn.query
    assert "ELSE 1.0" in conn.query
    assert "OFFICIAL_TEXT_RETRIEVED" in conn.query
    assert "MANUALLY_VERIFIED" in conn.query
    assert "SERVICE_PUBLIC_PART" not in conn.query.split("CASE", 1)[1].split("END AS authority_weight", 1)[0]
    assert "INSTITUTIONAL_GUIDANCE" not in conn.query.split("CASE", 1)[1].split("END AS authority_weight", 1)[0]
