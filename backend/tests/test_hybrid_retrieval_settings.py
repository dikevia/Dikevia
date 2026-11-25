from datetime import date

import pytest

from app.legal_corpus import VECTOR_HNSW_EF_SEARCH, search_legal_corpus


class _Transaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class _Connection:
    def __init__(self):
        self.calls = []

    def transaction(self):
        self.calls.append(("transaction", None))
        return _Transaction()

    async def execute(self, query):
        self.calls.append(("execute", query))

    async def fetch(self, query, *args):
        self.calls.append(("fetch", (query, args)))
        return []


@pytest.mark.asyncio
async def test_hybrid_retrieval_raises_hnsw_candidate_breadth_transaction_locally():
    connection = _Connection()
    embedding = [1.0] + [0.0] * 383

    result = await search_legal_corpus(
        connection, "alpha beta", date(2026, 11, 25),
        query_embedding=embedding,
    )

    assert result == []
    assert connection.calls[0] == ("transaction", None)
    assert connection.calls[1] == (
        "execute", f"SET LOCAL hnsw.ef_search = {VECTOR_HNSW_EF_SEARCH}"
    )
    assert connection.calls[2][0] == "fetch"


@pytest.mark.asyncio
async def test_lexical_only_retrieval_does_not_change_vector_session_settings():
    connection = _Connection()

    result = await search_legal_corpus(
        connection, "alpha beta", date(2026, 11, 25),
    )

    assert result == []
    assert [kind for kind, _ in connection.calls] == ["fetch"]
