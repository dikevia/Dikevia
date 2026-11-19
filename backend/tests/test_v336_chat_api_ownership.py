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


def test_chat_and_dossier_queries_bind_both_organization_and_owner():
    """Application SQL must retain explicit ownership even if PostgreSQL RLS is misconfigured."""
    conn = HiddenRowsConnection()
    ctx = context(conn)
    conversation_id = str(uuid4())

    asyncio.run(endpoint("/api/v1/chat/conversations", "GET")(ctx))
    asyncio.run(endpoint(
        "/api/v1/chat/conversations/{conversation_id}/messages", "GET"
    )(conversation_id, ctx))
    with pytest.raises(HTTPException):
        asyncio.run(endpoint(
            "/api/v1/chat/conversations/{conversation_id}", "DELETE"
        )(conversation_id, ctx))
    with pytest.raises(HTTPException):
        asyncio.run(endpoint(
            "/api/v1/chat/conversations/{conversation_id}/dossier", "POST"
        )(conversation_id, ctx))
    with pytest.raises(HTTPException):
        asyncio.run(endpoint(
            "/api/v1/chat/conversations/{conversation_id}/dossier", "GET"
        )(conversation_id, ctx))

    list_query, list_args = conn.fetch_calls[0]
    messages_query, messages_args = conn.fetch_calls[1]
    assert "c.organization_id=$1::uuid" in list_query
    assert "c.user_id=$2::uuid" in list_query
    assert list_args == (ctx.organization_id, ctx.user_id)
    assert "c.organization_id=$2::uuid" in messages_query
    assert "c.user_id=$3::uuid" in messages_query
    assert "m.organization_id=$2::uuid" in messages_query
    assert "m.user_id=$3::uuid" in messages_query
    assert messages_args == (conversation_id, ctx.organization_id, ctx.user_id)

    delete_query, delete_args = conn.execute_calls[0]
    assert "organization_id=$2::uuid" in delete_query
    assert "user_id=$3::uuid" in delete_query
    assert delete_args == (conversation_id, ctx.organization_id, ctx.user_id)

    dossier_lookup = conn.fetchrow_calls[0]
    assert "organization_id=$2::uuid" in dossier_lookup[0]
    assert "user_id=$3::uuid" in dossier_lookup[0]
    assert dossier_lookup[1] == (conversation_id, ctx.organization_id, ctx.user_id)
    dossier_read = conn.fetchrow_calls[1]
    assert "organization_id=$2::uuid" in dossier_read[0]
    assert "user_id=$3::uuid" in dossier_read[0]
    assert dossier_read[1] == (conversation_id, ctx.organization_id, ctx.user_id)


def test_chat_ask_and_dossier_update_sql_include_explicit_owner_scope():
    import inspect
    from app.main import ask, update_legal_dossier
    from app.dossiers import build_dossier_content

    ask_source = inspect.getsource(ask)
    assert "organization_id=$2::uuid AND user_id=$3::uuid" in ask_source
    assert "organization_id=$3::uuid AND user_id=$4::uuid" in ask_source
    assert "WHERE id=$1::uuid AND organization_id=$2::uuid AND user_id=$3::uuid" in ask_source

    conn = HiddenRowsConnection()
    ctx = context(conn)
    dossier = build_dossier_content(
        {"title": "Dossier test"},
        [{"role": "user", "content": "Question juridique de test"}],
    )
    with pytest.raises(HTTPException) as exc:
        asyncio.run(update_legal_dossier(
            str(uuid4()), {"content": dossier}, ctx
        ))
    assert exc.value.status_code == 404
    query, args = conn.fetchrow_calls[0]
    assert "organization_id=$2::uuid AND user_id=$3::uuid" in query
    assert args[1:] == (ctx.organization_id, ctx.user_id)


def test_local_document_ai_review_is_gated_by_explicit_opt_in():
    import inspect
    from app.main import review_local_rule_compliance

    source = inspect.getsource(review_local_rule_compliance)
    assert "settings.ai_local_document_review_enabled" in source
    assert "if (usable_national and settings.ai_api_base_url and settings.ai_api_key and settings.ai_model" in source


@pytest.mark.asyncio
async def test_chat_tenant_dependency_releases_transaction_and_clears_session_context(monkeypatch):
    from app import dependencies

    class Transaction:
        def __init__(self, connection):
            self.connection = connection

        async def __aenter__(self):
            self.connection.transaction_depth += 1

        async def __aexit__(self, exc_type, exc, tb):
            self.connection.transaction_depth -= 1

    class Connection:
        def __init__(self):
            self.transaction_depth = 0
            self.execute_calls = []
            self.terminated = False

        def transaction(self):
            return Transaction(self)

        async def execute(self, query, *args):
            self.execute_calls.append((query, args))

        async def fetchrow(self, query, *args):
            return {"user_id": uuid4(), "role": "MEMBER"}

        def terminate(self):
            self.terminated = True

    class Acquire:
        def __init__(self, connection):
            self.connection = connection

        async def __aenter__(self):
            return self.connection

        async def __aexit__(self, exc_type, exc, tb):
            return False

    class Pool:
        def __init__(self, connection):
            self.connection = connection

        def acquire(self):
            return Acquire(self.connection)

    conn = Connection()
    monkeypatch.setattr(dependencies, "get_pool", lambda: Pool(conn))
    principal = SimpleNamespace(issuer="https://issuer.example", subject="subject-1")
    generator = dependencies.get_tenant_context_for_chat(principal, str(uuid4()))

    ctx = await generator.__anext__()
    assert ctx.conn is conn
    assert conn.transaction_depth == 0
    assert any("set_config('app.current_org_id',$1,false)" in call[0]
               for call in conn.execute_calls)

    await generator.aclose()
    assert conn.terminated is False
    assert "set_config('app.current_org_id','',false)" in conn.execute_calls[-1][0]


@pytest.mark.asyncio
async def test_chat_endpoint_does_not_hold_transaction_during_orchestration(monkeypatch):
    from app import main as main_module
    from app.schemas import AskRequest, AskResponse

    class Transaction:
        def __init__(self, connection):
            self.connection = connection

        async def __aenter__(self):
            assert self.connection.transaction_depth == 0
            self.connection.transaction_depth += 1

        async def __aexit__(self, exc_type, exc, tb):
            self.connection.transaction_depth -= 1

    class Connection:
        def __init__(self):
            self.transaction_depth = 0

        def transaction(self):
            return Transaction(self)

        async def fetchrow(self, query, *args):
            return {"id": uuid4()}

        async def fetchval(self, query, *args):
            return uuid4()

        async def fetch(self, query, *args):
            return []

        async def execute(self, query, *args):
            return "UPDATE 1"

    conn = Connection()
    ctx = context(conn)
    monkeypatch.setattr(
        main_module, "consume_chat_request",
        lambda *args: _async_allowed_decision(),
    )

    async def fake_orchestrator_ask(*args, **kwargs):
        assert conn.transaction_depth == 0
        return AskResponse(
            request_id=str(uuid4()), verification_status="NON_VERIFIE",
            answer="Réponse documentaire de test.",
        )

    monkeypatch.setattr(main_module.orchestrator, "ask", fake_orchestrator_ask)
    payload = AskRequest(
        employer="NATIONAL",
        question="Question juridique suffisamment longue pour le test.",
    )

    result = await main_module.ask(payload, ctx)

    assert result.verification_status == "NON_VERIFIE"
    assert conn.transaction_depth == 0


async def _async_allowed_decision():
    return SimpleNamespace(allowed=True, retry_after_seconds=0)


def test_local_compliance_review_uses_short_transaction_dependency():
    import inspect
    from app.main import review_local_rule_compliance

    source = inspect.getsource(review_local_rule_compliance)
    assert "get_tenant_context_for_chat" in source
    assert "async with ctx.conn.transaction():" in source
    assert "await analyze_question(" in source
    # The model call is not nested in a transaction block: the route only opens
    # short transactions for rate limiting, usage metering and audit persistence.
    assert source.index("await analyze_question(") > source.index("async with ctx.conn.transaction():")
    assert source.count("async with ctx.conn.transaction():") == 4
