from pathlib import Path

import pytest
from fastapi import HTTPException

ROOT = Path(__file__).parents[2]


def _route(source: str, marker: str, next_marker: str) -> str:
    return source.split(marker, 1)[1].split(next_marker, 1)[0]


def test_direct_piste_endpoints_share_the_tenant_user_quota_before_network_calls():
    source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    cases = [
        ('@app.post("/api/v1/integrations/legifrance/check"', "await legifrance.ping()", '@app.get("/api/v1/legal/legifrance/search"'),
        ('@app.get("/api/v1/legal/legifrance/search"', "await legifrance.search_code_articles", '@app.get("/api/v1/legal/jurisprudence/administrative/search"'),
        ('@app.get("/api/v1/legal/jurisprudence/administrative/search"', "await case_law_connector.search", '@app.get("/api/v1/legal/jurisprudence/administrative/{decision_id}"'),
        ('@app.get("/api/v1/legal/jurisprudence/administrative/{decision_id}"', "await case_law_connector.consult", '@app.get("/api/v1/legal/knowledge/search"'),
    ]
    for marker, outbound_call, next_marker in cases:
        route = _route(source, marker, next_marker)
        assert "await enforce_legal_connector_rate_limit(ctx)" in route
        assert route.index("await enforce_legal_connector_rate_limit(ctx)") < route.index(outbound_call)


def test_connector_search_inputs_are_validated_before_consuming_the_quota():
    source = (ROOT / "backend/app/main.py").read_text(encoding="utf-8")
    for marker, next_marker in [
        ('@app.get("/api/v1/legal/legifrance/search"', '@app.get("/api/v1/legal/jurisprudence/administrative/search"'),
        ('@app.get("/api/v1/legal/jurisprudence/administrative/search"', '@app.get("/api/v1/legal/jurisprudence/administrative/{decision_id}"'),
    ]:
        route = _route(source, marker, next_marker)
        assert route.index("len(q.strip()) < 2") < route.index("await enforce_legal_connector_rate_limit(ctx)")


@pytest.mark.asyncio
async def test_shared_connector_limiter_returns_retry_after_when_quota_is_exhausted(monkeypatch):
    from app import main
    from app.rate_limit import RateLimitDecision

    class Context:
        organization_id = "00000000-0000-0000-0000-000000000001"
        user_id = "00000000-0000-0000-0000-000000000002"
        conn = object()

    async def denied(*args):
        return RateLimitDecision(allowed=False, request_count=11, retry_after_seconds=23)

    monkeypatch.setattr(main, "consume_chat_request", denied)
    with pytest.raises(HTTPException) as caught:
        await main.enforce_legal_connector_rate_limit(Context())

    assert caught.value.status_code == 429
    assert caught.value.headers == {"Retry-After": "23"}
