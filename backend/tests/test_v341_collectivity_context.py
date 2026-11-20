from datetime import date
from uuid import uuid4

import pytest

from app.local_corpus import search_local_documents
from app.schemas import AskRequest


def test_chat_request_accepts_a_tenant_collectivity_id():
    collectivity_id = uuid4()
    request = AskRequest(
        employer="NATIONAL",
        question="Quelle règle locale s'applique à cette situation ?",
        collectivity_id=collectivity_id,
    )
    assert request.collectivity_id == collectivity_id


@pytest.mark.asyncio
async def test_local_document_search_uses_selected_collectivity_and_tenant_scope():
    class RecordingConnection:
        def __init__(self):
            self.query = None
            self.args = None

        async def fetch(self, query, *args):
            self.query = query
            self.args = args
            return []

    conn = RecordingConnection()
    organization_id = str(uuid4())
    collectivity_id = str(uuid4())

    result = await search_local_documents(
        conn,
        organization_id,
        "NATIONAL",
        "temps de travail",
        date(2025, 1, 1),
        collectivity_id=collectivity_id,
    )

    assert result == []
    assert "dt.organization_id=$1::uuid" in conn.query
    assert "c.id=$6::uuid" in conn.query
    assert conn.args[0] == organization_id
    assert conn.args[5] == collectivity_id


@pytest.mark.asyncio
async def test_national_chat_without_selected_collectivity_does_not_search_local_documents():
    class ConnectionMustNotBeUsed:
        async def fetch(self, *args):
            raise AssertionError("Aucun document local ne doit être recherché.")

    assert await search_local_documents(
        ConnectionMustNotBeUsed(),
        str(uuid4()),
        "NATIONAL",
        "question nationale",
        date(2025, 1, 1),
    ) == []
