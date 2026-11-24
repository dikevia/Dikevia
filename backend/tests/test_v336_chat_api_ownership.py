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



@pytest.mark.parametrize("restricted_status", ["VALIDE_HUMAINEMENT", "CLOTURE"])
def test_member_cannot_human_validate_or_close_a_legal_dossier(restricted_status):
    from app.dossiers import build_dossier_content

    class ExistingDossierConnection(HiddenRowsConnection):
        async def fetchrow(self, query, *args):
            self.fetchrow_calls.append((query, args))
            return {"id": uuid4(), "content": {"status": "BROUILLON_A_VALIDER"}}

    conn = ExistingDossierConnection()
    ctx = context(conn)
    dossier = build_dossier_content({"title": "Dossier test"}, [
        {"role": "user", "content": "Question de test"}
    ])
    dossier["status"] = restricted_status
    route = endpoint(
        "/api/v1/chat/conversations/{conversation_id}/dossier", "PUT"
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(route(str(uuid4()), {"content": dossier}, ctx))

    assert exc.value.status_code == 403
    assert "responsables habilités" in exc.value.detail
    assert len(conn.fetchrow_calls) == 1
    assert not conn.execute_calls


@pytest.mark.parametrize("privileged_role", ["ORG_ADMIN", "LEGAL_EDITOR"])
@pytest.mark.parametrize("privileged_status", ["VALIDE_HUMAINEMENT", "CLOTURE"])
def test_privileged_roles_can_human_validate_or_close_a_legal_dossier(
    privileged_role, privileged_status
):
    from app.dossiers import build_dossier_content

    class UpdatableDossierConnection(HiddenRowsConnection):
        def __init__(self):
            super().__init__()
            self.updated_content = None

        async def fetchrow(self, query, *args):
            self.fetchrow_calls.append((query, args))
            if query.lstrip().startswith("SELECT"):
                return {"id": uuid4(), "content": {"status": "BROUILLON_A_VALIDER"}}
            self.updated_content = args[1]
            import json
            return {
                "id": uuid4(),
                "content": json.loads(self.updated_content),
                "created_at": None,
                "updated_at": None,
            }

    conn = UpdatableDossierConnection()
    ctx = context(conn)
    ctx.role = privileged_role
    dossier = build_dossier_content(
        {"title": "Dossier test"},
        [{"role": "user", "content": "Question de test"}],
    )
    dossier["status"] = privileged_status
    route = endpoint(
        "/api/v1/chat/conversations/{conversation_id}/dossier", "PUT"
    )

    result = asyncio.run(route(str(uuid4()), {"content": dossier}, ctx))

    assert result["content"]["status"] == privileged_status
    assert len(conn.fetchrow_calls) == 2
    assert "UPDATE legal_dossiers" in conn.fetchrow_calls[1][0]


@pytest.mark.parametrize("stored_status", ["VALIDE_HUMAINEMENT", "CLOTURE"])
def test_member_cannot_reopen_or_modify_a_finalized_legal_dossier(stored_status):
    from app.dossiers import build_dossier_content

    class FinalizedDossierConnection(HiddenRowsConnection):
        async def fetchrow(self, query, *args):
            self.fetchrow_calls.append((query, args))
            return {"id": uuid4(), "content": {"status": stored_status}}

    conn = FinalizedDossierConnection()
    ctx = context(conn)
    dossier = build_dossier_content(
        {"title": "Dossier test"},
        [{"role": "user", "content": "Question de test"}],
    )
    dossier["status"] = "BROUILLON_A_VALIDER"
    route = endpoint(
        "/api/v1/chat/conversations/{conversation_id}/dossier", "PUT"
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(route(str(uuid4()), {"content": dossier}, ctx))

    assert exc.value.status_code == 403
    assert "réouverture" in exc.value.detail
    assert len(conn.fetchrow_calls) == 1
    assert not conn.execute_calls

class ConversationScopeConnection:
    def __init__(self, public_service="FPT", conversation_exists=True):
        self.public_service = public_service
        self.conversation_exists = conversation_exists
        self.calls = []

    async def fetchrow(self, query, *args):
        self.calls.append((query, args))
        if "FOR UPDATE" in query:
            return {"id": args[0]} if self.conversation_exists else None
        if self.public_service == "NO_MESSAGES":
            return None
        return {"public_service": (
            None if self.public_service == "NO_METADATA" else self.public_service
        )}


def test_chat_turn_cannot_switch_public_service_inside_existing_conversation():
    from app.main import _lock_conversation_for_chat_turn

    conn = ConversationScopeConnection("FPT")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_lock_conversation_for_chat_turn(
            conn, str(uuid4()), str(uuid4()), str(uuid4()), "FPH",
        ))

    assert exc.value.status_code == 409
    assert "nouvelle conversation" in exc.value.detail
    assert len(conn.calls) == 2
    assert "FOR UPDATE" in conn.calls[0][0]
    assert "metadata->>'public_service'" in conn.calls[1][0]


def test_chat_turn_keeps_existing_public_service_in_conversation():
    from app.main import _lock_conversation_for_chat_turn

    conn = ConversationScopeConnection("FPE")
    asyncio.run(_lock_conversation_for_chat_turn(
        conn, str(uuid4()), str(uuid4()), str(uuid4()), "FPE",
    ))
    assert len(conn.calls) == 2


def test_legacy_conversation_without_public_service_defaults_to_fpt():
    from app.main import _lock_conversation_for_chat_turn

    conn = ConversationScopeConnection("NO_METADATA")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_lock_conversation_for_chat_turn(
            conn, str(uuid4()), str(uuid4()), str(uuid4()), "FPE",
        ))
    assert exc.value.status_code == 409

def test_empty_conversation_defaults_to_fpt_after_row_lock():
    from app.main import _lock_conversation_for_chat_turn

    conn = ConversationScopeConnection("NO_MESSAGES")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_lock_conversation_for_chat_turn(
            conn, str(uuid4()), str(uuid4()), str(uuid4()), "FPH",
        ))
    assert exc.value.status_code == 409
    assert len(conn.calls) == 2


def test_unknown_conversation_is_rejected_before_reading_branch_metadata():
    from app.main import _lock_conversation_for_chat_turn

    conn = ConversationScopeConnection(conversation_exists=False)
    with pytest.raises(HTTPException) as exc:
        asyncio.run(_lock_conversation_for_chat_turn(
            conn, str(uuid4()), str(uuid4()), str(uuid4()), "FPT",
        ))
    assert exc.value.status_code == 404
    assert len(conn.calls) == 1

