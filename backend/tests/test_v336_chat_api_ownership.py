"""API-level ownership contracts for persistent conversations and legal dossiers.

These tests exercise the route handlers with an RLS-shaped connection:
rows hidden by PostgreSQL RLS appear absent. Real PostgreSQL RLS behavior is
covered separately by test_postgres_rls_integration.py.
"""
import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.main import app


class HiddenRowsConnection:
    """A minimal connection whose RLS-protected reads expose no foreign rows."""

    def __init__(self):
        self.fetch_calls = []
        self.fetchrow_calls = []
        self.execute_calls = []

    async def fetch(self, query, *args):
        self.fetch_calls.append((query, args))
        return []

    async def fetchrow(self, query, *args):
        self.fetchrow_calls.append((query, args))
        return None

    async def execute(self, query, *args):
        self.execute_calls.append((query, args))
        return "DELETE 0"


def endpoint(path, method):
    route = next(
        route for route in app.routes
        if getattr(route, "path", None) == path
        and method in getattr(route, "methods", set())
    )
    return route.endpoint


def context(conn):
    return SimpleNamespace(
        conn=conn,
        organization_id=str(uuid4()),
        user_id=str(uuid4()),
        role="MEMBER",
    )


def test_foreign_or_unknown_conversation_is_not_listed_or_read():
    conn = HiddenRowsConnection()
    ctx = context(conn)
    list_route = endpoint("/api/v1/chat/conversations", "GET")
    messages_route = endpoint(
        "/api/v1/chat/conversations/{conversation_id}/messages", "GET"
    )
    conversation_id = str(uuid4())

    listed = asyncio.run(list_route(ctx))
    messages = asyncio.run(messages_route(conversation_id, ctx))

    assert listed == []
    assert messages == []
    assert len(conn.fetch_calls) == 2
    assert all("chat_conversations" in call[0] for call in conn.fetch_calls)


def test_foreign_or_unknown_conversation_cannot_be_deleted():
    conn = HiddenRowsConnection()
    ctx = context(conn)
    delete_route = endpoint("/api/v1/chat/conversations/{conversation_id}", "DELETE")

    with pytest.raises(HTTPException) as exc:
        asyncio.run(delete_route(str(uuid4()), ctx))

    assert exc.value.status_code == 404
    assert conn.execute_calls
    assert "DELETE FROM chat_conversations" in conn.execute_calls[0][0]


@pytest.mark.parametrize("method", ["POST", "GET", "PUT"])
def test_foreign_or_unknown_conversation_cannot_create_read_or_update_dossier(method):
    conn = HiddenRowsConnection()
    ctx = context(conn)
    conversation_id = str(uuid4())

    if method == "POST":
        route = endpoint(
            "/api/v1/chat/conversations/{conversation_id}/dossier", "POST"
        )
        call = route(conversation_id, ctx)
    elif method == "GET":
        route = endpoint(
            "/api/v1/chat/conversations/{conversation_id}/dossier", "GET"
        )
        call = route(conversation_id, ctx)
    else:
        route = endpoint(
            "/api/v1/chat/conversations/{conversation_id}/dossier", "PUT"
        )
        call = route(conversation_id, {"content": {"status": "BROUILLON_A_VALIDER"}}, ctx)

    with pytest.raises(HTTPException) as exc:
        asyncio.run(call)

    assert exc.value.status_code == 404
    assert conn.fetchrow_calls


def test_api_routes_are_bound_to_authenticated_tenant_context():
    expected = {
        ("/api/v1/chat/conversations", "GET"),
        ("/api/v1/chat/conversations", "POST"),
        ("/api/v1/chat/conversations/{conversation_id}/messages", "GET"),
        ("/api/v1/chat/conversations/{conversation_id}", "DELETE"),
        ("/api/v1/chat/conversations/{conversation_id}/dossier", "POST"),
        ("/api/v1/chat/conversations/{conversation_id}/dossier", "GET"),
        ("/api/v1/chat/conversations/{conversation_id}/dossier", "PUT"),
    }
    actual = {
        (route.path, method)
        for route in app.routes
        if hasattr(route, "path")
        for method in getattr(route, "methods", set())
        if route.path.startswith("/api/v1/chat/conversations")
    }
    assert expected <= actual
